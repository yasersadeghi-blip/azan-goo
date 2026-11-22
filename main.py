# -*- coding: utf-8 -*-
"""
اذان‌گو - برنامه اعلام اوقات شرعی برای ویندوز
نسخه: 1.1
"""

import os
import sys
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import config as cfgmod
from core import cities, prayer_calc, persian_date, autostart, audio_player
from core.scheduler import AzanScheduler

APP_TITLE = "اذان‌گو"
DAYS_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه", "شنبه", "یکشنبه"]
# نگاشت به Python weekday: دوشنبه=0 ... یکشنبه=6

# ------------------------------------------------------------------ #
# پالت رنگی و فونت‌ها (تم سبز-طلایی، الهام‌گرفته از هنر اسلامی)
# ------------------------------------------------------------------ #
BG = "#0B2E28"           # زمینه اصلی (سبز تیره)
BG_ALT = "#0E3A32"       # زمینه ثانویه / نوار وضعیت
CARD_BG = "#123F37"      # زمینه کارت‌ها
CARD_BG_HOVER = "#16493F"
CARD_BORDER = "#1F5A4D"
NEXT_CARD_BG = "#1B4A3E"
GOLD = "#D4AF37"
GOLD_LIGHT = "#E8CE7B"
GOLD_DARK = "#B4922B"
TEXT = "#F5F1E6"
TEXT_MUTED = "#9FC1B7"
DANGER = "#C0564B"

FONT_FAMILY = "Tahoma"
FONT_NORMAL = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_BOLD = (FONT_FAMILY, 11, "bold")
FONT_BIG = (FONT_FAMILY, 16, "bold")
FONT_TITLE = (FONT_FAMILY, 20, "bold")
FONT_HERO_TIME = (FONT_FAMILY, 28, "bold")
FONT_COUNTDOWN = (FONT_FAMILY, 13, "bold")

PRAYER_ICONS = {
    "fajr": "🌄", "sunrise": "🌅", "dhuhr": "☀️",
    "asr": "🌤️", "sunset": "🌇", "maghrib": "🌆", "isha": "🌙",
}

def _legacy_windows():
    """ویندوز ۷/۸ فونت ایموجی ندارد؛ در این سیستم‌ها نمادهای تصویری حذف می‌شوند."""
    try:
        return sys.platform.startswith("win") and sys.getwindowsversion().major < 10
    except Exception:
        return False


LEGACY_UI = _legacy_windows()


def clean_text(text):
    """در ویندوز ۷ ایموجی/نمادهای تصویری را حذف می‌کند (نیم‌فاصله و حروف فارسی دست‌نخورده می‌مانند)."""
    if not LEGACY_UI or not isinstance(text, str):
        return text
    out = []
    for ch in text:
        o = ord(ch)
        if 0x2190 <= o <= 0x2BFF or 0xFE00 <= o <= 0xFE0F or o >= 0x1F000:
            continue
        out.append(ch)
    return "".join(out).strip()


def sanitize_widgets(widget):
    """پیمایش بازگشتی ویجت‌ها و پاک‌سازی متن آن‌ها برای ویندوز ۷."""
    if not LEGACY_UI:
        return
    try:
        if "text" in widget.keys():
            old = str(widget.cget("text"))
            new = clean_text(old)
            if new != old:
                widget.configure(text=new)
    except Exception:
        pass
    for child in widget.winfo_children():
        sanitize_widgets(child)


# روش‌های محاسبه مناسب برای مذهب شیعه اثنی‌عشری (۱۲ امامی)
METHOD_LABELS_FA = {
    "Jafari": "جعفری (شیعه اثنی‌عشری)",
    "Tehran": "تهران (مؤسسه ژئوفیزیک)",
}
METHOD_LABELS_FA_REV = {v: k for k, v in METHOD_LABELS_FA.items()}


class AzanApp:
    def __init__(self, root):
        self.root = root
        self.cfg = cfgmod.load_config()
        self.root.title(APP_TITLE)
        self.root.geometry(self.cfg.get("window_geometry") or "820x680")
        self.root.minsize(720, 560)
        self.root.configure(bg=BG)
        try:
            self.root.option_add("*Font", FONT_NORMAL)
        except Exception:
            pass
        self._set_window_icon()
        self._setup_style()

        self.scheduler = AzanScheduler(get_config=lambda: self.cfg, on_status=self._set_status)

        self._build_ui()
        self._refresh_times_view()
        self._last_refreshed_date = date.today()
        self.scheduler.start()
        self._tick_ui()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ================================================================== #
    def _set_window_icon(self):
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        try:
            if sys.platform.startswith("win") and os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

    def _setup_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", background=BG, foreground=TEXT, font=FONT_NORMAL)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=FONT_NORMAL)
        style.configure("Card.TLabel", background=CARD_BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED, font=FONT_SMALL)
        style.configure("CardMuted.TLabel", background=CARD_BG, foreground=TEXT_MUTED, font=FONT_SMALL)
        style.configure("Title.TLabel", background=BG, foreground=GOLD, font=FONT_TITLE)
        style.configure("Bold.TLabel", background=BG, foreground=TEXT, font=FONT_BOLD)
        style.configure("Gold.TLabel", background=BG, foreground=GOLD_LIGHT, font=FONT_BOLD)

        style.configure("TLabelframe", background=BG, foreground=GOLD_LIGHT, borderwidth=1,
                         relief="solid", bordercolor=CARD_BORDER)
        style.configure("TLabelframe.Label", background=BG, foreground=GOLD_LIGHT, font=FONT_BOLD)

        style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(6, 6, 6, 0))
        style.configure("TNotebook.Tab", background=BG_ALT, foreground=TEXT_MUTED,
                         padding=(18, 10), font=FONT_BOLD, borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", CARD_BG)],
                  foreground=[("selected", GOLD_LIGHT)])

        style.configure("TButton", background=CARD_BORDER, foreground=TEXT, padding=(10, 6),
                         font=FONT_NORMAL, borderwidth=0, focuscolor=CARD_BORDER)
        style.map("TButton", background=[("active", "#2A6E5D")])

        style.configure("Accent.TButton", background=GOLD, foreground="#1B2A22",
                         padding=(12, 7), font=FONT_BOLD, borderwidth=0)
        style.map("Accent.TButton", background=[("active", GOLD_LIGHT)])

        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=FONT_NORMAL)
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TRadiobutton", background=BG, foreground=TEXT, font=FONT_NORMAL)
        style.map("TRadiobutton", background=[("active", BG)])

        style.configure("TEntry", fieldbackground=CARD_BG, foreground=TEXT,
                         insertcolor=TEXT, bordercolor=CARD_BORDER, borderwidth=1,
                         padding=6)
        style.map("TEntry", fieldbackground=[("readonly", CARD_BG)])

        style.configure("TCombobox", fieldbackground=CARD_BG, background=CARD_BG,
                         foreground=TEXT, arrowcolor=GOLD_LIGHT, bordercolor=CARD_BORDER,
                         padding=5)
        style.map("TCombobox",
                  fieldbackground=[("readonly", CARD_BG)],
                  foreground=[("readonly", TEXT)],
                  selectbackground=[("readonly", CARD_BG)],
                  selectforeground=[("readonly", TEXT)])
        self.root.option_add("*TCombobox*Listbox.background", CARD_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", GOLD_DARK)
        self.root.option_add("*TCombobox*Listbox.font", FONT_NORMAL)

        style.configure("TSpinbox", fieldbackground=CARD_BG, foreground=TEXT,
                         arrowcolor=GOLD_LIGHT, bordercolor=CARD_BORDER, padding=5)

        style.configure("Horizontal.TScale", background=BG, troughcolor=CARD_BG)

        style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG,
                         foreground=TEXT, rowheight=28, borderwidth=0, font=FONT_NORMAL)
        style.configure("Treeview.Heading", background=BG_ALT, foreground=GOLD_LIGHT,
                         font=FONT_BOLD, borderwidth=0)
        style.map("Treeview", background=[("selected", GOLD_DARK)], foreground=[("selected", "#1B2A22")])

        style.configure("TSeparator", background=CARD_BORDER)

    # ================================================================== #
    # ساخت رابط کاربری
    # ================================================================== #
    def _build_ui(self):
        header = ttk.Frame(self.root, style="TFrame")
        header.pack(fill="x", padx=0, pady=0)
        header_inner = tk.Frame(header, bg=BG, padx=18, pady=14)
        header_inner.pack(fill="x")
        title_lbl = ttk.Label(header_inner, text="🕌  اذان‌گو", style="Title.TLabel")
        title_lbl.pack(side="right")
        self.date_var = tk.StringVar()
        ttk.Label(header_inner, textvariable=self.date_var, style="Muted.TLabel",
                  font=FONT_BOLD).pack(side="left")
        ttk.Separator(self.root, orient="horizontal").pack(fill="x")

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_main = ttk.Frame(nb, style="TFrame")
        self.tab_sound = ttk.Frame(nb, style="TFrame")
        self.tab_schedule = ttk.Frame(nb, style="TFrame")
        self.tab_general = ttk.Frame(nb, style="TFrame")

        nb.add(self.tab_main, text="اوقات شرعی")
        nb.add(self.tab_sound, text="تنظیمات صدا")
        nb.add(self.tab_schedule, text="پخش زمان‌بندی‌شده")
        nb.add(self.tab_general, text="عمومی")

        self._build_tab_main(self.tab_main)
        self._build_tab_sound(self.tab_sound)
        self._build_tab_schedule(self.tab_schedule)
        self._build_tab_general(self.tab_general)
        sanitize_widgets(self.root)

        # نوار وضعیت
        self.status_var = tk.StringVar(value="آماده")
        status_bar = tk.Frame(self.root, bg=BG_ALT)
        status_bar.pack(fill="x", side="bottom")
        tk.Label(status_bar, textvariable=self.status_var, anchor="e", bg=BG_ALT, fg=TEXT_MUTED,
                 font=FONT_SMALL, padx=12, pady=5).pack(fill="x")

    # ---------------------------------------------------------------- #
    def _build_tab_main(self, parent):
        # --- نوار ابزار: شهر / روش محاسبه / مذهب / موقعیت دلخواه ---
        toolbar = tk.Frame(parent, bg=CARD_BG, padx=14, pady=12,
                            highlightbackground=CARD_BORDER, highlightthickness=1)
        toolbar.pack(fill="x", pady=(0, 12))

        def toolbar_field(col, label_text, widget_factory):
            wrap = tk.Frame(toolbar, bg=CARD_BG)
            wrap.grid(row=0, column=col, padx=10, sticky="e")
            ttk.Label(wrap, text=label_text, style="CardMuted.TLabel").pack(anchor="e")
            w = widget_factory(wrap)
            w.pack(anchor="e", pady=(2, 0))
            return w

        self.city_var = tk.StringVar(value=self.cfg.get("city", "تهران"))
        city_combo = toolbar_field(2, "شهر", lambda p: ttk.Combobox(
            p, textvariable=self.city_var, values=cities.get_city_names(), state="readonly", width=16))
        city_combo.bind("<<ComboboxSelected>>", self._on_city_changed)

        method_key = self.cfg.get("method", "Jafari")
        self.method_var = tk.StringVar(value=METHOD_LABELS_FA.get(method_key, METHOD_LABELS_FA["Jafari"]))
        method_combo = toolbar_field(1, "روش محاسبه (مذهب شیعه)", lambda p: ttk.Combobox(
            p, textvariable=self.method_var, values=list(METHOD_LABELS_FA.values()),
            state="readonly", width=22))
        method_combo.bind("<<ComboboxSelected>>", self._on_method_changed)

        wrap0 = tk.Frame(toolbar, bg=CARD_BG)
        wrap0.grid(row=0, column=0, padx=10, sticky="e")
        ttk.Label(wrap0, text=" ", style="CardMuted.TLabel").pack(anchor="e")
        ttk.Button(wrap0, text="📍 موقعیت دلخواه...", command=self._open_custom_location_dialog).pack(anchor="e", pady=(2, 0))

        for i in range(3):
            toolbar.grid_columnconfigure(i, weight=1)

        # --- کارت «نماز بعدی» با شمارش معکوس زنده ---
        hero = tk.Frame(parent, bg=NEXT_CARD_BG, highlightbackground=GOLD, highlightthickness=1)
        hero.pack(fill="x", pady=(0, 14))
        hero_inner = tk.Frame(hero, bg=NEXT_CARD_BG, pady=16)
        hero_inner.pack(fill="x")
        ttk.Label(hero_inner, text="نماز بعدی", background=NEXT_CARD_BG, foreground=TEXT_MUTED,
                  font=FONT_BOLD, anchor="center").pack()
        self.next_name_var = tk.StringVar(value="در حال محاسبه...")
        ttk.Label(hero_inner, textvariable=self.next_name_var, background=NEXT_CARD_BG, foreground=GOLD,
                  font=FONT_TITLE, anchor="center").pack(pady=(4, 0))
        self.next_time_var = tk.StringVar(value="--:--")
        ttk.Label(hero_inner, textvariable=self.next_time_var, background=NEXT_CARD_BG, foreground=TEXT,
                  font=FONT_HERO_TIME, anchor="center").pack()
        self.countdown_var = tk.StringVar(value="")
        ttk.Label(hero_inner, textvariable=self.countdown_var, background=NEXT_CARD_BG, foreground=GOLD_LIGHT,
                  font=FONT_COUNTDOWN, anchor="center").pack(pady=(2, 0))

        # --- شبکه کارت‌های اوقات شرعی ---
        times_label = ttk.Label(parent, text="اوقات شرعی امروز  (برای ویرایش دستی، روی عدد کلیک کنید)",
                                 style="Bold.TLabel")
        times_label.pack(anchor="e", pady=(0, 8))

        grid_wrap = tk.Frame(parent, bg=BG)
        grid_wrap.pack(fill="x")

        self.time_entries = {}
        keys = ["fajr", "sunrise", "dhuhr", "asr", "sunset", "maghrib", "isha"]
        cols = 4
        for i in range(cols):
            grid_wrap.grid_columnconfigure(i, weight=1, uniform="cards")

        for idx, key in enumerate(keys):
            r, c = divmod(idx, cols)
            card = tk.Frame(grid_wrap, bg=CARD_BG, highlightbackground=CARD_BORDER,
                             highlightthickness=1, padx=8, pady=10)
            card.grid(row=r, column=c, padx=6, pady=6, sticky="nsew")

            ttk.Label(card, text=PRAYER_ICONS.get(key, ""), background=CARD_BG,
                      font=(FONT_FAMILY, 20), anchor="center").pack()
            ttk.Label(card, text=prayer_calc.PRAYER_LABELS_FA.get(key, key), style="Card.TLabel",
                      font=FONT_BOLD, anchor="center").pack(pady=(2, 6))

            var = tk.StringVar()
            entry = ttk.Entry(card, textvariable=var, width=8, justify="center", font=FONT_BOLD)
            entry.pack()
            self.time_entries[key] = var

            if key in ("fajr", "dhuhr", "asr", "maghrib", "isha"):
                ttk.Button(card, text="▶ پخش آزمایشی", command=lambda k=key: self._test_play(k)).pack(
                    pady=(8, 0), fill="x")

        btns = tk.Frame(parent, bg=BG)
        btns.pack(fill="x", pady=14)
        ttk.Button(btns, text="ذخیره ویرایش‌های دستی", style="Accent.TButton",
                   command=self._save_manual_overrides).pack(side="right", padx=4)
        ttk.Button(btns, text="بازگشت به مقادیر محاسبه‌شده",
                   command=self._reset_overrides).pack(side="right", padx=4)

    def _on_city_changed(self, event=None):
        self.cfg["city"] = self.city_var.get()
        self.cfg["custom_location"] = None
        cfgmod.save_config(self.cfg)
        self.scheduler._today = None
        self._refresh_times_view()

    def _on_method_changed(self, event=None):
        self.cfg["method"] = METHOD_LABELS_FA_REV.get(self.method_var.get(), "Jafari")
        cfgmod.save_config(self.cfg)
        self.scheduler._today = None
        self._refresh_times_view()

    def _open_custom_location_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("موقعیت جغرافیایی دلخواه")
        win.geometry("340x260")
        win.configure(bg=BG)
        try:
            win.transient(self.root)
        except Exception:
            pass

        ttk.Label(win, text="📍 موقعیت جغرافیایی دلخواه", style="Gold.TLabel").pack(pady=(16, 10))

        ttk.Label(win, text="عرض جغرافیایی (Latitude):").pack(pady=(4, 2))
        lat_var = tk.StringVar()
        ttk.Entry(win, textvariable=lat_var, justify="center").pack()

        ttk.Label(win, text="طول جغرافیایی (Longitude):").pack(pady=(10, 2))
        lng_var = tk.StringVar()
        ttk.Entry(win, textvariable=lng_var, justify="center").pack()

        ttk.Label(win, text="اختلاف با UTC (مثلاً 3.5):").pack(pady=(10, 2))
        tz_var = tk.StringVar(value="3.5")
        ttk.Entry(win, textvariable=tz_var, justify="center").pack()

        if self.cfg.get("custom_location"):
            loc = self.cfg["custom_location"]
            lat_var.set(str(loc["lat"]))
            lng_var.set(str(loc["lng"]))
            tz_var.set(str(loc["tz"]))

        def apply():
            try:
                lat = float(lat_var.get())
                lng = float(lng_var.get())
                tz = float(tz_var.get())
            except ValueError:
                messagebox.showerror(APP_TITLE, "لطفاً مقادیر عددی معتبر وارد کنید.")
                return
            self.cfg["custom_location"] = {"lat": lat, "lng": lng, "tz": tz}
            cfgmod.save_config(self.cfg)
            self.scheduler._today = None
            self._refresh_times_view()
            win.destroy()

        ttk.Button(win, text="اعمال", style="Accent.TButton", command=apply).pack(pady=16)
        sanitize_widgets(win)



    def _test_play(self, key):
        self.scheduler.play_now(key, cfg=self.cfg)

    def _save_manual_overrides(self):
        today_key = date.today().isoformat()
        overrides = self.cfg.setdefault("manual_overrides", {})
        day_overrides = {}
        computed = self.scheduler.compute_times_for(date.today(), {**self.cfg, "manual_overrides": {}})
        for key, var in self.time_entries.items():
            val = var.get().strip()
            if val and val != computed.get(key):
                day_overrides[key] = val
        overrides[today_key] = day_overrides
        cfgmod.save_config(self.cfg)
        self.scheduler._today = None
        self._refresh_times_view()
        self._set_status("ویرایش‌های دستی ذخیره شد.")

    def _reset_overrides(self):
        today_key = date.today().isoformat()
        self.cfg.get("manual_overrides", {}).pop(today_key, None)
        cfgmod.save_config(self.cfg)
        self.scheduler._today = None
        self._refresh_times_view()
        self._set_status("به مقادیر محاسبه‌شده بازگردانده شد.")

    def _refresh_times_view(self):
        self.date_var.set(f"{persian_date.today_jalali_str()}   |   {date.today().strftime('%Y-%m-%d')} میلادی")
        times = self.scheduler.get_today_times()
        for key, var in self.time_entries.items():
            var.set(times.get(key, "--:--"))

    # ---------------------------------------------------------------- #
    def _build_tab_sound(self, parent):
        frame = ttk.LabelFrame(parent, text="🔊 فایل صوتی پیش‌فرض اذان")
        frame.pack(fill="x", padx=10, pady=10)
        self.default_azan_var = tk.StringVar(value=self.cfg.get("default_azan_file", ""))
        self._file_row(frame, "فایل پیش‌فرض:", self.default_azan_var, self._pick_default_azan)

        frame2 = ttk.LabelFrame(parent, text="🕌 فایل اذان اختصاصی برای هر نماز (اختیاری)")
        frame2.pack(fill="x", padx=10, pady=10)
        self.azan_file_vars = {}
        for key in ["fajr", "dhuhr", "asr", "maghrib", "isha"]:
            var = tk.StringVar(value=self.cfg.get("azan_files", {}).get(key, ""))
            self.azan_file_vars[key] = var
            self._file_row(frame2, prayer_calc.PRAYER_LABELS_FA[key] + ":", var,
                            lambda k=key: self._pick_azan_file(k))

        frame3 = ttk.LabelFrame(parent, text="⏱️ صدای پیش‌اذان (پخش آن دقیقاً طوری زمان‌بندی می‌شود که بلافاصله پس از پایانش، اذان پخش شود)")
        frame3.pack(fill="x", padx=10, pady=10)
        self.pre_enabled_var = tk.BooleanVar(value=self.cfg.get("pre_azan_enabled", False))
        ttk.Checkbutton(frame3, text="فعال باشد", variable=self.pre_enabled_var,
                         command=self._save_sound_settings).pack(anchor="e", padx=10, pady=4)
        self.pre_azan_var = tk.StringVar(value=self.cfg.get("pre_azan_file", ""))
        self._file_row(frame3, "فایل صوتی:", self.pre_azan_var, self._pick_pre_azan)

        note = ttk.Label(
            frame3, anchor="e", justify="right", wraplength=680,
            text=("طول این فایل صوتی به‌طور خودکار تشخیص داده می‌شود و پخش آن به‌گونه‌ای "
                  "شروع می‌شود که دقیقاً هم‌زمان با رسیدن وقت اذان، به پایان برسد و بلافاصله "
                  "اذان پخش شود.")
        )
        note.pack(fill="x", padx=10, pady=(0, 4))

        row = ttk.Frame(frame3)
        row.pack(fill="x", padx=10, pady=6)
        ttk.Label(row, text="در صورت عدم امکان تشخیص طول فایل، چند دقیقه قبل از اذان پخش شود:").pack(side="right")
        self.pre_minutes_var = tk.StringVar(value=str(self.cfg.get("pre_azan_minutes", 10)))
        spin = ttk.Spinbox(row, from_=1, to=60, textvariable=self.pre_minutes_var, width=6,
                            command=self._save_sound_settings)
        spin.pack(side="right", padx=8)

        frame4 = ttk.LabelFrame(parent, text="🔈 صدا")
        frame4.pack(fill="x", padx=10, pady=10)
        row4 = ttk.Frame(frame4)
        row4.pack(fill="x", padx=10, pady=6)
        ttk.Label(row4, text="میزان صدا:").pack(side="right")
        self.volume_var = tk.DoubleVar(value=self.cfg.get("volume", 0.8) * 100)
        scale = ttk.Scale(row4, from_=0, to=100, variable=self.volume_var, orient="horizontal",
                           command=lambda e: self._save_sound_settings())
        scale.pack(side="right", fill="x", expand=True, padx=8)

        ttk.Button(parent, text="💾 ذخیره تنظیمات صدا", style="Accent.TButton",
                   command=self._save_sound_settings).pack(pady=14)

    def _file_row(self, parent, label, var, on_browse):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=4)
        ttk.Label(row, text=label, width=14, anchor="e").pack(side="right")
        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="right", fill="x", expand=True, padx=6)
        ttk.Button(row, text="انتخاب فایل...", command=on_browse).pack(side="right", padx=4)

    def _browse_audio(self):
        return filedialog.askopenfilename(
            title="انتخاب فایل صوتی",
            filetypes=[("فایل‌های صوتی", "*.mp3 *.wav *.ogg"), ("همه فایل‌ها", "*.*")],
        )

    def _pick_default_azan(self):
        f = self._browse_audio()
        if f:
            self.default_azan_var.set(f)
            self._save_sound_settings()

    def _pick_azan_file(self, key):
        f = self._browse_audio()
        if f:
            self.azan_file_vars[key].set(f)
            self._save_sound_settings()

    def _pick_pre_azan(self):
        f = self._browse_audio()
        if f:
            self.pre_azan_var.set(f)
            self._save_sound_settings()

    def _save_sound_settings(self):
        self.cfg["default_azan_file"] = self.default_azan_var.get()
        self.cfg["azan_files"] = {k: v.get() for k, v in self.azan_file_vars.items()}
        self.cfg["pre_azan_enabled"] = self.pre_enabled_var.get()
        self.cfg["pre_azan_file"] = self.pre_azan_var.get()
        try:
            self.cfg["pre_azan_minutes"] = int(float(self.pre_minutes_var.get()))
        except ValueError:
            self.cfg["pre_azan_minutes"] = 10
        self.cfg["volume"] = float(self.volume_var.get()) / 100.0
        cfgmod.save_config(self.cfg)
        self._set_status("تنظیمات صدا ذخیره شد.")

    # ---------------------------------------------------------------- #
    def _build_tab_schedule(self, parent):
        ttk.Label(parent,
                  text=("پخش خودکار فایل صوتی در یک ساعت ثابت، یا نسبت به یکی از اذان‌ها "
                        "(مثلاً «۱۰ دقیقه بعد از اذان مغرب» یا «۱۵ دقیقه قبل از اذان صبح»)"),
                  font=FONT_BOLD, anchor="e", justify="right", wraplength=700).pack(fill="x", padx=10, pady=8)

        cols = ("time", "label", "days", "file", "enabled")
        self.sched_tree = ttk.Treeview(parent, columns=cols, show="headings", height=10)
        for c, txt, w in [("time", "زمان", 150), ("label", "عنوان", 120),
                           ("days", "روزها", 150), ("file", "فایل", 220), ("enabled", "فعال", 50)]:
            self.sched_tree.heading(c, text=txt)
            self.sched_tree.column(c, width=w, anchor="center")
        self.sched_tree.pack(fill="both", expand=True, padx=10, pady=6)

        btns = ttk.Frame(parent)
        btns.pack(fill="x", padx=10, pady=6)
        ttk.Button(btns, text="➕ افزودن...", style="Accent.TButton",
                   command=self._add_schedule_item).pack(side="right", padx=4)
        ttk.Button(btns, text="ویرایش...", command=self._edit_schedule_item).pack(side="right", padx=4)
        ttk.Button(btns, text="حذف", command=self._remove_schedule_item).pack(side="right", padx=4)

        self._reload_schedule_tree()

    def _reload_schedule_tree(self):
        self.sched_tree.delete(*self.sched_tree.get_children())
        for item in self.cfg.get("custom_schedule", []):
            days_txt = "همه روزها" if not item.get("days") else ",".join(
                DAYS_FA[d] for d in item.get("days", []))
            time_txt = self._describe_schedule_time(item)
            self.sched_tree.insert("", "end", iid=item["id"], values=(
                time_txt, item.get("label", ""), days_txt,
                os.path.basename(item.get("file", "")) or "-",
                "بله" if item.get("enabled", True) else "خیر",
            ))

    @staticmethod
    def _describe_schedule_time(item):
        if item.get("mode") == "relative":
            prayer_label = prayer_calc.PRAYER_LABELS_FA.get(item.get("relative_prayer"), "?")
            offset = item.get("relative_offset_minutes", 0)
            direction = "قبل از" if item.get("relative_direction") == "before" else "بعد از"
            return f"{offset} دقیقه {direction} {prayer_label}"
        return item.get("time", "")

    def _add_schedule_item(self):
        self._schedule_dialog(None)

    def _edit_schedule_item(self):
        sel = self.sched_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        item = next((i for i in self.cfg.get("custom_schedule", []) if i["id"] == item_id), None)
        if item:
            self._schedule_dialog(item)

    def _remove_schedule_item(self):
        sel = self.sched_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        self.cfg["custom_schedule"] = [i for i in self.cfg.get("custom_schedule", []) if i["id"] != item_id]
        cfgmod.save_config(self.cfg)
        self._reload_schedule_tree()

    def _schedule_dialog(self, item):
        win = tk.Toplevel(self.root)
        win.title("برنامه صوتی")
        win.geometry("400x580")
        win.configure(bg=BG)
        try:
            win.transient(self.root)
        except Exception:
            pass

        ttk.Label(win, text="🔔 برنامه صوتی", style="Gold.TLabel").pack(pady=(14, 4))
        ttk.Label(win, text="عنوان:").pack(pady=(8, 2))
        label_var = tk.StringVar(value=(item or {}).get("label", ""))
        ttk.Entry(win, textvariable=label_var, justify="center").pack(fill="x", padx=20)

        # --- نوع زمان‌بندی: ساعت ثابت / نسبت به اذان ---
        mode_var = tk.StringVar(value=(item or {}).get("mode", "fixed"))
        mode_frame = ttk.LabelFrame(win, text="نوع زمان‌بندی")
        mode_frame.pack(fill="x", padx=20, pady=(12, 6))
        ttk.Radiobutton(mode_frame, text="ساعت ثابت روزانه", variable=mode_var,
                         value="fixed", command=lambda: switch_mode()).pack(anchor="e", padx=8, pady=3)
        ttk.Radiobutton(mode_frame, text="نسبت به یکی از اذان‌ها", variable=mode_var,
                         value="relative", command=lambda: switch_mode()).pack(anchor="e", padx=8, pady=3)

        # --- حالت ساعت ثابت ---
        fixed_frame = ttk.Frame(win)
        ttk.Label(fixed_frame, text="ساعت (HH:MM):").pack(pady=(6, 2))
        time_var = tk.StringVar(value=(item or {}).get("time", "12:00"))
        ttk.Entry(fixed_frame, textvariable=time_var, justify="center").pack()

        # --- حالت نسبت به اذان ---
        relative_frame = ttk.Frame(win)
        ttk.Label(relative_frame, text="اذان مرجع:").pack(pady=(6, 2))
        prayer_var = tk.StringVar(
            value=prayer_calc.PRAYER_LABELS_FA.get((item or {}).get("relative_prayer", "maghrib"), "اذان مغرب"))
        prayer_names = {prayer_calc.PRAYER_LABELS_FA[k]: k for k in ["fajr", "dhuhr", "asr", "maghrib", "isha"]}
        ttk.Combobox(relative_frame, textvariable=prayer_var, values=list(prayer_names.keys()),
                     state="readonly", justify="center").pack()

        offset_row = ttk.Frame(relative_frame)
        offset_row.pack(pady=8)
        ttk.Label(offset_row, text="دقیقه:").pack(side="right", padx=4)
        offset_var = tk.StringVar(value=str((item or {}).get("relative_offset_minutes", 10)))
        ttk.Spinbox(offset_row, from_=0, to=180, textvariable=offset_var, width=6).pack(side="right", padx=4)
        direction_var = tk.StringVar(
            value="قبل از اذان" if (item or {}).get("relative_direction") == "before" else "بعد از اذان")
        ttk.Combobox(offset_row, textvariable=direction_var,
                     values=["قبل از اذان", "بعد از اذان"], state="readonly", width=12).pack(side="right", padx=4)

        def switch_mode():
            if mode_var.get() == "fixed":
                relative_frame.pack_forget()
                fixed_frame.pack(fill="x")
            else:
                fixed_frame.pack_forget()
                relative_frame.pack(fill="x")

        switch_mode()

        ttk.Label(win, text="فایل صوتی:").pack(pady=(12, 2))
        file_var = tk.StringVar(value=(item or {}).get("file", ""))
        file_row = ttk.Frame(win)
        file_row.pack(fill="x", padx=20)
        ttk.Entry(file_row, textvariable=file_var).pack(side="right", fill="x", expand=True)

        def browse():
            f = self._browse_audio()
            if f:
                file_var.set(f)
        ttk.Button(file_row, text="...", width=3, command=browse).pack(side="right", padx=4)

        ttk.Label(win, text="روزهای هفته (خالی = همه روزها):").pack(pady=(12, 2))
        day_vars = []
        day_frame = ttk.Frame(win)
        day_frame.pack()
        existing_days = set((item or {}).get("days", []))
        for idx, name in enumerate(DAYS_FA):
            v = tk.BooleanVar(value=idx in existing_days)
            day_vars.append(v)
            ttk.Checkbutton(day_frame, text=name, variable=v).grid(
                row=idx // 4, column=idx % 4, sticky="e", padx=4, pady=2)

        enabled_var = tk.BooleanVar(value=(item or {}).get("enabled", True))
        ttk.Checkbutton(win, text="فعال", variable=enabled_var).pack(pady=10)

        def save():
            mode = mode_var.get()
            days = [i for i, v in enumerate(day_vars) if v.get()]
            new_item = {
                "id": (item or {}).get("id", str(uuid.uuid4())),
                "label": label_var.get().strip(),
                "mode": mode,
                "file": file_var.get().strip(),
                "days": days,
                "enabled": enabled_var.get(),
            }
            if mode == "fixed":
                t = time_var.get().strip()
                try:
                    datetime.strptime(t, "%H:%M")
                except ValueError:
                    messagebox.showerror(APP_TITLE, "ساعت باید به فرمت HH:MM باشد (مثلاً 14:30)")
                    return
                new_item["time"] = t
            else:
                try:
                    offset = int(float(offset_var.get()))
                except ValueError:
                    messagebox.showerror(APP_TITLE, "مقدار دقیقه باید عددی باشد.")
                    return
                new_item["relative_prayer"] = prayer_names.get(prayer_var.get(), "maghrib")
                new_item["relative_offset_minutes"] = offset
                new_item["relative_direction"] = "before" if direction_var.get() == "قبل از اذان" else "after"

            sched = self.cfg.setdefault("custom_schedule", [])
            if item:
                for i, existing in enumerate(sched):
                    if existing["id"] == new_item["id"]:
                        sched[i] = new_item
                        break
            else:
                sched.append(new_item)
            cfgmod.save_config(self.cfg)
            self._reload_schedule_tree()
            win.destroy()

        ttk.Button(win, text="ذخیره", style="Accent.TButton", command=save).pack(pady=10)
        sanitize_widgets(win)

    # ---------------------------------------------------------------- #
    def _build_tab_general(self, parent):
        frame = ttk.LabelFrame(parent, text="⚙️ عمومی")
        frame.pack(fill="x", padx=10, pady=10)

        self.auto_play_var = tk.BooleanVar(value=self.cfg.get("auto_play_azan", True))
        ttk.Checkbutton(frame, text="پخش خودکار اذان در ساعت شرعی", variable=self.auto_play_var,
                         command=self._save_general_settings).pack(anchor="e", padx=10, pady=6)

        self.autostart_var = tk.BooleanVar(value=autostart.is_enabled() or self.cfg.get("autostart", False))
        ttk.Checkbutton(frame, text="اجرای خودکار برنامه هنگام روشن شدن ویندوز", variable=self.autostart_var,
                         command=self._toggle_autostart).pack(anchor="e", padx=10, pady=6)

        info = ttk.Label(
            parent,
            justify="right", anchor="e", wraplength=680,
            text=("راهنما:\n"
                  "- اوقات شرعی بر اساس محاسبات نجومی (طلوع/غروب خورشید) برای شهر یا موقعیت انتخابی محاسبه می‌شود.\n"
                  "- برای اجرای خودکار در پس‌زمینه، گزینه «اجرای خودکار هنگام روشن شدن ویندوز» را فعال کنید و "
                  "برنامه را کوچک (Minimize) نگه دارید، نبندید.\n"
                  "- در صورت تمایل به تغییر صدای اذان، از تب «تنظیمات صدا» فایل صوتی دلخواه خود را انتخاب کنید.\n"
                  "- می‌توانید برای اوقات مذهبی خاص (دعا، مناجات و ...) از تب «پخش زمان‌بندی‌شده» استفاده کنید."),
        )
        info.pack(fill="x", padx=14, pady=14)

        ttk.Button(parent, text="باز کردن پوشه تنظیمات", command=self._open_config_dir).pack(pady=6)

    def _save_general_settings(self):
        self.cfg["auto_play_azan"] = self.auto_play_var.get()
        cfgmod.save_config(self.cfg)

    def _toggle_autostart(self):
        ok, err = autostart.set_enabled(self.autostart_var.get())
        if not ok:
            messagebox.showwarning(APP_TITLE, err)
            self.autostart_var.set(not self.autostart_var.get())
            return
        self.cfg["autostart"] = self.autostart_var.get()
        cfgmod.save_config(self.cfg)

    def _open_config_dir(self):
        path = cfgmod.get_config_dir()
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)
            else:
                self._set_status(f"مسیر تنظیمات: {path}")
        except Exception:
            self._set_status(f"مسیر تنظیمات: {path}")

    # ================================================================== #
    def _set_status(self, message):
        def _update():
            self.status_var.set(message)
        try:
            self.root.after(0, _update)
        except Exception:
            pass

    def _tick_ui(self):
        # اگر روز عوض شده باشد، جدول اوقات شرعی را دوباره محاسبه و نمایش می‌دهیم
        today = date.today()
        if getattr(self, "_last_refreshed_date", None) != today:
            self._refresh_times_view()
            self._last_refreshed_date = today

        name, t, remaining = self._compute_next_prayer_info()
        self.next_name_var.set(name)
        self.next_time_var.set(t)
        total_seconds = max(0, int(remaining.total_seconds()))
        hh = total_seconds // 3600
        mm = (total_seconds % 3600) // 60
        ss = total_seconds % 60
        self.countdown_var.set(clean_text(f"⏳ {hh:02d}:{mm:02d}:{ss:02d} تا اذان"))
        self.root.after(1000, self._tick_ui)

    def _compute_next_prayer_info(self):
        times = self.scheduler.get_today_times()
        now = datetime.now()
        today = now.date()
        order = ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]
        for key in order:
            t = times.get(key)
            if not t:
                continue
            try:
                dt = datetime.combine(today, datetime.strptime(t, "%H:%M").time())
            except ValueError:
                continue
            if dt > now:
                return prayer_calc.PRAYER_LABELS_FA.get(key, key), t, dt - now
        fajr = times.get("fajr")
        if fajr:
            try:
                tomorrow = today + timedelta(days=1)
                dt = datetime.combine(tomorrow, datetime.strptime(fajr, "%H:%M").time())
                return prayer_calc.PRAYER_LABELS_FA.get("fajr", "fajr"), f"{fajr} (فردا)", dt - now
            except ValueError:
                pass
        return "—", "--:--", timedelta(0)

    def _on_close(self):
        self.cfg["window_geometry"] = self.root.geometry()
        cfgmod.save_config(self.cfg)
        self.scheduler.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = AzanApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
