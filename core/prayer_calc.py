# -*- coding: utf-8 -*-
"""
موتور محاسبه اوقات شرعی (اذان) بر اساس فرمول‌های نجومی استاندارد
(موقعیت خورشید با دقت پایین/متوسط - همان روشی که در نرم‌افزارهای اوقات شرعی رایج است)

روش‌های محاسبه پشتیبانی‌شده (زاویه‌ها بر حسب درجه):
    - Tehran   : مؤسسه ژئوفیزیک دانشگاه تهران (فجر 17.7، عشا 14، مغرب با زاویه 4.5 بعد از غروب)
    - Jafari   : شیعه اثنی‌عشری (فجر 16، عشا 14، مغرب با زاویه 4)
    - MWL      : رابطه جهانی مسلمانان (فجر 18، عشا 17)
    - ISNA     : انجمن اسلامی آمریکای شمالی (فجر 15، عشا 15)
    - Egypt    : هیئت مساحی مصر (فجر 19.5، عشا 17.5)
    - Karachi  : دانشگاه علوم اسلامی کراچی (فجر 18، عشا 18)
    - Makkah   : ام القری مکه (فجر 18.5، عشا = 90 دقیقه بعد از مغرب)
"""

import math
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# تعریف روش‌های محاسبه: (fajr_angle, isha_angle_or_None, isha_minutes_after_maghrib,
#                          maghrib_angle_or_None, maghrib_minutes_after_sunset)
# ---------------------------------------------------------------------------
METHODS = {
    "Tehran":  {"fajr": 17.7, "isha_angle": 14.0, "isha_minutes": None,
                "maghrib_angle": 4.5, "maghrib_minutes": None},
    "Jafari":  {"fajr": 16.0, "isha_angle": 14.0, "isha_minutes": None,
                "maghrib_angle": 4.0, "maghrib_minutes": None},
    "MWL":     {"fajr": 18.0, "isha_angle": 17.0, "isha_minutes": None,
                "maghrib_angle": None, "maghrib_minutes": 0},
    "ISNA":    {"fajr": 15.0, "isha_angle": 15.0, "isha_minutes": None,
                "maghrib_angle": None, "maghrib_minutes": 0},
    "Egypt":   {"fajr": 19.5, "isha_angle": 17.5, "isha_minutes": None,
                "maghrib_angle": None, "maghrib_minutes": 0},
    "Karachi": {"fajr": 18.0, "isha_angle": 18.0, "isha_minutes": None,
                "maghrib_angle": None, "maghrib_minutes": 0},
    "Makkah":  {"fajr": 18.5, "isha_angle": None, "isha_minutes": 90,
                "maghrib_angle": None, "maghrib_minutes": 0},
}

DEFAULT_METHOD = "Jafari"   # مناسب برای شیعیان اثنی‌عشری (۱۲ امامی)
SUNRISE_ANGLE = 0.833       # شکست جوی + قطر خورشید
ASR_SHAFII = 1
ASR_HANAFI = 2


def _d2r(d):
    return math.radians(d)


def _r2d(r):
    return math.degrees(r)


def _fix_hour(h):
    h = h % 24
    if h < 0:
        h += 24
    return h


def _fix_deg(a):
    a = a % 360
    if a < 0:
        a += 360
    return a


def _julian_date(y, m, d):
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    return jd


def _sun_position(jd):
    """موقعیت خورشید: (declination, equation_of_time بر حسب دقیقه)
    jd باید معادل ظهرِ روز مورد نظر به وقت UT باشد."""
    d = (jd + 0.5) - 2451545.0
    g = _fix_deg(357.529 + 0.98560028 * d)
    q = _fix_deg(280.459 + 0.98564736 * d)
    l = _fix_deg(q + 1.915 * math.sin(_d2r(g)) + 0.020 * math.sin(_d2r(2 * g)))

    e = 23.439 - 0.00000036 * d

    ra = _r2d(math.atan2(math.cos(_d2r(e)) * math.sin(_d2r(l)), math.cos(_d2r(l)))) / 15.0
    ra = _fix_hour(ra)
    decl = _r2d(math.asin(math.sin(_d2r(e)) * math.sin(_d2r(l))))

    eq_t = q / 15.0 - ra
    # نرمال‌سازی به بازه [-0.5, 0.5] ساعت
    if eq_t > 0.5:
        eq_t -= 1
    elif eq_t < -0.5:
        eq_t += 1

    return decl, eq_t * 60.0  # دقیقه


def _time_for_angle(angle, latitude, decl, is_before_noon):
    """زاویه‌ی خورشید زیر افق -> فاصله زمانی از ظهر (ساعت)، برای طلوع/فجر/غروب/عشا"""
    lat_r = _d2r(latitude)
    decl_r = _d2r(decl)
    val = (-math.sin(_d2r(angle)) - math.sin(lat_r) * math.sin(decl_r)) / (
        math.cos(lat_r) * math.cos(decl_r)
    )
    val = max(-1.0, min(1.0, val))
    h = _r2d(math.acos(val)) / 15.0
    return -h if is_before_noon else h


def _asr_time_correct(shadow_factor, latitude, decl):
    """محاسبه صحیح زمان عصر با روش سایه (شافعی=1، حنفی=2)"""
    lat_r = _d2r(latitude)
    decl_r = _d2r(decl)
    # ارتفاع خورشید هنگام عصر
    t = math.atan(1.0 / (shadow_factor + math.tan(abs(lat_r - decl_r))))
    altitude = _r2d(t)
    val = (math.sin(_d2r(altitude)) - math.sin(lat_r) * math.sin(decl_r)) / (
        math.cos(lat_r) * math.cos(decl_r)
    )
    val = max(-1.0, min(1.0, val))
    h = _r2d(math.acos(val)) / 15.0
    return h


def calculate_prayer_times(d: date, latitude: float, longitude: float,
                            timezone_offset: float, method: str = DEFAULT_METHOD,
                            asr_factor: int = ASR_SHAFII):
    """
    محاسبه اوقات شرعی برای یک روز و یک موقعیت جغرافیایی مشخص.
    خروجی: دیکشنری با کلیدهای fajr, sunrise, dhuhr, asr, sunset, maghrib, isha
    مقادیر بر حسب ساعتِ اعشاری محلی (بر اساس timezone_offset داده‌شده).
    """
    cfg = METHODS.get(method, METHODS[DEFAULT_METHOD])
    jd = _julian_date(d.year, d.month, d.day) - longitude / (15.0 * 24.0)

    decl, eq_t = _sun_position(jd)

    dhuhr = _fix_hour(12 + timezone_offset - longitude / 15.0 - eq_t / 60.0)

    fajr = dhuhr + _time_for_angle(cfg["fajr"], latitude, decl, True)
    sunrise = dhuhr + _time_for_angle(SUNRISE_ANGLE, latitude, decl, True)
    sunset = dhuhr + _time_for_angle(SUNRISE_ANGLE, latitude, decl, False)

    if cfg["maghrib_angle"] is not None:
        maghrib = dhuhr + _time_for_angle(cfg["maghrib_angle"], latitude, decl, False)
    else:
        maghrib = sunset + (cfg["maghrib_minutes"] or 0) / 60.0

    if cfg["isha_angle"] is not None:
        isha = dhuhr + _time_for_angle(cfg["isha_angle"], latitude, decl, False)
    else:
        isha = maghrib + (cfg["isha_minutes"] or 0) / 60.0

    asr = dhuhr + _asr_time_correct(asr_factor, latitude, decl)

    return {
        "fajr": _fix_hour(fajr),
        "sunrise": _fix_hour(sunrise),
        "dhuhr": _fix_hour(dhuhr),
        "asr": _fix_hour(asr),
        "sunset": _fix_hour(sunset),
        "maghrib": _fix_hour(maghrib),
        "isha": _fix_hour(isha),
    }


def hours_to_hhmm(h: float) -> str:
    total_minutes = round(h * 60)
    hh = (total_minutes // 60) % 24
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


PRAYER_LABELS_FA = {
    "fajr": "اذان صبح",
    "sunrise": "طلوع آفتاب",
    "dhuhr": "اذان ظهر",
    "asr": "اذان عصر",
    "sunset": "غروب آفتاب",
    "maghrib": "اذان مغرب",
    "isha": "اذان عشا",
}

if __name__ == "__main__":
    # تست سریع: تهران، امروز (روش پیش‌فرض: جعفری - شیعه اثنی‌عشری)
    today = date.today()
    times = calculate_prayer_times(today, 35.6892, 51.3890, 3.5)
    for k, v in times.items():
        print(PRAYER_LABELS_FA.get(k, k), hours_to_hhmm(v))
