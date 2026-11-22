# -*- coding: utf-8 -*-
"""ذخیره و بازیابی تنظیمات برنامه در یک فایل JSON در پوشه AppData کاربر"""

import json
import os
import sys

APP_NAME = "AzanGoo"


def get_config_dir():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/.config")
    path = os.path.join(base, APP_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_config_path():
    return os.path.join(get_config_dir(), "config.json")


DEFAULT_CONFIG = {
    "city": "تهران",
    "custom_location": None,          # {"lat":..,"lng":..,"tz":..} در صورت انتخاب شهر دلخواه
    "method": "Jafari",               # جعفری (شیعه اثنی‌عشری) — پیش‌فرض مناسب مذهب شیعه
    "asr_factor": 1,
    "manual_overrides": {},           # {"YYYY-MM-DD": {"fajr": "04:33", ...}}
    "auto_play_azan": True,
    "azan_files": {                   # فایل صوتی اذان برای هر نماز (اگر خالی باشد از default استفاده می‌شود)
        "fajr": "", "dhuhr": "", "asr": "", "maghrib": "", "isha": ""
    },
    "default_azan_file": "",
    "pre_azan_file": "",
    "pre_azan_minutes": 10,
    "pre_azan_enabled": False,
    "custom_schedule": [],            # [{"id":.., "time":"HH:MM", "file":"...", "days":[0..6], "enabled":true, "label":""}]
    "autostart": False,
    "volume": 0.8,
    "window_geometry": None,
}


def load_config():
    path = get_config_path()
    if not os.path.exists(path):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_CONFIG)
        merged.update(data)
        return merged
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
