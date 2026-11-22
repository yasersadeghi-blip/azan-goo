# -*- coding: utf-8 -*-
"""
موتور زمان‌بند: هر ثانیه یک‌بار زمان فعلی را با اوقات شرعی امروز و برنامه‌های
صوتی دلخواه مقایسه می‌کند و در لحظه مناسب صدا را پخش می‌کند.

ویژگی‌های کلیدی:
- صدای پیش‌اذان بر اساس «طول واقعی فایل صوتی» زمان‌بندی می‌شود؛ یعنی پخش آن طوری
  آغاز می‌شود که دقیقاً هم‌زمان با پایانش، وقت اذان فرا برسد و اذان بلافاصله پخش شود.
- برنامه‌های صوتی دلخواه می‌توانند نسبت به یکی از اذان‌ها (مثلاً «۱۰ دقیقه بعد از
  اذان مغرب» یا «۱۵ دقیقه قبل از اذان صبح») تعریف شوند، یا در یک ساعت ثابت روزانه.
"""

import os
import threading
import time
from datetime import date, datetime, timedelta

from . import prayer_calc, audio_player, cities

CHECK_INTERVAL_SECONDS = 1
TRIGGER_WINDOW_SECONDS = 2.0   # بازه‌ی مجاز برای تشخیص «رسیدن» به یک زمان هدف

AZAN_KEYS = ["fajr", "dhuhr", "asr", "maghrib", "isha"]


class AzanScheduler:
    def __init__(self, get_config, on_status=None):
        """
        get_config: تابعی که دیکشنری تنظیمات جاری را برمی‌گرداند (خواندن زنده تنظیمات)
        on_status: callback(message:str) برای گزارش وضعیت به رابط کاربری
        """
        self._get_config = get_config
        self._on_status = on_status or (lambda msg: None)
        self._thread = None
        self._running = False
        self._today = None
        self._today_times = {}
        self._triggered_today = set()   # کلیدهای اذانی که امروز پخش شده‌اند
        self._triggered_pre_today = set()
        self._triggered_custom = set()  # (date_str, schedule_id)
        self._duration_cache = {}       # file_path -> (mtime, duration_seconds)

    # ------------------------------------------------------------------ #
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------ #
    def get_location(self, cfg):
        if cfg.get("custom_location"):
            loc = cfg["custom_location"]
            return loc["lat"], loc["lng"], loc["tz"]
        city = cities.get_city(cfg.get("city", "تهران"))
        if city is None:
            city = cities.get_city("تهران")
        return city

    def compute_times_for(self, d: date, cfg):
        lat, lng, tz = self.get_location(cfg)
        times = prayer_calc.calculate_prayer_times(
            d, lat, lng, tz,
            method=cfg.get("method", "Tehran"),
            asr_factor=cfg.get("asr_factor", 1),
        )
        overrides = cfg.get("manual_overrides", {}).get(d.isoformat(), {})
        hhmm = {k: prayer_calc.hours_to_hhmm(v) for k, v in times.items()}
        for k, v in overrides.items():
            if v:
                hhmm[k] = v
        return hhmm

    def get_today_times(self):
        cfg = self._get_config()
        today = date.today()
        if self._today != today:
            self._refresh_day(cfg, today)
        return dict(self._today_times)

    def _refresh_day(self, cfg, today):
        self._today = today
        self._today_times = self.compute_times_for(today, cfg)
        self._triggered_today = set()
        self._triggered_pre_today = set()

    # ------------------------------------------------------------------ #
    def _get_duration(self, file_path):
        """طول فایل صوتی را با کش بر اساس زمان آخرین تغییر فایل برمی‌گرداند."""
        if not file_path or not os.path.exists(file_path):
            return None
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return None
        cached = self._duration_cache.get(file_path)
        if cached and cached[0] == mtime:
            return cached[1]
        duration = audio_player.get_duration_seconds(file_path)
        self._duration_cache[file_path] = (mtime, duration)
        return duration

    @staticmethod
    def _hhmm_to_dt(today, hhmm):
        try:
            tm = datetime.strptime(hhmm, "%H:%M").time()
        except (ValueError, TypeError):
            return None
        return datetime.combine(today, tm)

    @staticmethod
    def _reached(now, target_dt):
        """آیا لحظه‌ی فعلی دقیقاً به زمان هدف رسیده (در یک بازه کوتاه و تازه)؟"""
        if target_dt is None:
            return False
        diff = (now - target_dt).total_seconds()
        return 0 <= diff <= TRIGGER_WINDOW_SECONDS

    # ------------------------------------------------------------------ #
    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as e:
                self._on_status(f"خطای زمان‌بند: {e}")
            time.sleep(CHECK_INTERVAL_SECONDS)

    def _tick(self):
        cfg = self._get_config()
        now = datetime.now()
        today = now.date()

        if self._today != today:
            self._refresh_day(cfg, today)

        # --- اذان اصلی ---
        if cfg.get("auto_play_azan", True):
            for key in AZAN_KEYS:
                azan_dt = self._hhmm_to_dt(today, self._today_times.get(key))
                if key not in self._triggered_today and self._reached(now, azan_dt):
                    self._triggered_today.add(key)
                    self._play_azan(cfg, key)

        # --- صدای پیش‌اذان (بر اساس طول واقعی فایل) ---
        if cfg.get("pre_azan_enabled") and cfg.get("pre_azan_file"):
            for key in AZAN_KEYS:
                if key in self._triggered_pre_today:
                    continue
                azan_dt = self._hhmm_to_dt(today, self._today_times.get(key))
                if azan_dt is None:
                    continue
                start_dt = self._pre_azan_start_dt(cfg, azan_dt)
                if self._reached(now, start_dt):
                    self._triggered_pre_today.add(key)
                    self._on_status(
                        f"در حال پخش صدای پیش‌اذان، پایان هم‌زمان با {prayer_calc.PRAYER_LABELS_FA[key]}")
                    audio_player.play(cfg["pre_azan_file"], volume=cfg.get("volume", 0.8))

        # --- برنامه‌های صوتی دلخواه (زمان ثابت یا نسبت به یک اذان) ---
        for item in cfg.get("custom_schedule", []):
            if not item.get("enabled", True):
                continue
            target_dt = self._schedule_target_dt(item, today)
            if target_dt is None:
                continue
            days = item.get("days")
            if days and target_dt.weekday() not in set(days):
                continue
            trigger_key = (today.isoformat(), item.get("id"))
            if trigger_key in self._triggered_custom:
                continue
            if self._reached(now, target_dt):
                self._triggered_custom.add(trigger_key)
                label = item.get("label") or "برنامه دلخواه"
                self._on_status(f"در حال پخش: {label}")
                audio_player.play(item.get("file", ""), volume=cfg.get("volume", 0.8))

    # ------------------------------------------------------------------ #
    def _pre_azan_start_dt(self, cfg, azan_dt):
        """زمان دقیق شروع پخش پیش‌اذان: azan_dt منهای طول واقعی فایل صوتی.
        اگر طول فایل قابل تشخیص نباشد، از تعداد دقیقه‌ی تنظیم‌شده به‌صورت دستی استفاده می‌شود."""
        duration = self._get_duration(cfg.get("pre_azan_file"))
        if duration:
            return azan_dt - timedelta(seconds=duration)
        minutes = int(cfg.get("pre_azan_minutes", 10) or 0)
        return azan_dt - timedelta(minutes=minutes)

    def _schedule_target_dt(self, item, today):
        mode = item.get("mode", "fixed")
        if mode == "relative":
            prayer = item.get("relative_prayer")
            t = self._today_times.get(prayer)
            base_dt = self._hhmm_to_dt(today, t)
            if base_dt is None:
                return None
            offset = int(item.get("relative_offset_minutes", 0) or 0)
            delta = timedelta(minutes=offset)
            if item.get("relative_direction", "after") == "before":
                return base_dt - delta
            return base_dt + delta
        else:
            return self._hhmm_to_dt(today, item.get("time"))

    # ------------------------------------------------------------------ #
    def _play_azan(self, cfg, key):
        files = cfg.get("azan_files", {})
        file_path = files.get(key) or cfg.get("default_azan_file")
        label = prayer_calc.PRAYER_LABELS_FA.get(key, key)
        if not file_path:
            self._on_status(f"زمان {label} فرا رسید، اما فایل صوتی اذان تنظیم نشده است.")
            return
        self._on_status(f"در حال پخش {label} ({self._today_times.get(key)})")
        audio_player.play(file_path, volume=cfg.get("volume", 0.8))

    def play_now(self, key, cfg=None):
        """پخش دستیِ فوریِ یک اذان (برای دکمه «پخش آزمایشی»)"""
        cfg = cfg or self._get_config()
        self._play_azan(cfg, key)

    def next_prayer(self):
        """برمی‌گرداند: (نام فارسی، ساعت) نماز بعدی"""
        times = self.get_today_times()
        now_hhmm = datetime.now().strftime("%H:%M")
        order = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
        for key in order:
            t = times.get(key)
            if t and t > now_hhmm:
                return prayer_calc.PRAYER_LABELS_FA.get(key, key), t
        return prayer_calc.PRAYER_LABELS_FA.get("fajr", "fajr"), times.get("fajr", "--:--") + " (فردا)"
