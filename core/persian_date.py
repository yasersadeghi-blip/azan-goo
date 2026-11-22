# -*- coding: utf-8 -*-
"""کمک‌کننده تاریخ شمسی با استفاده از کتابخانه jdatetime"""

import jdatetime
from datetime import date

WEEKDAYS_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]


def today_jalali_str():
    j = jdatetime.date.today()
    weekday = WEEKDAYS_FA[j.weekday()]
    return f"{weekday}، {j.day} {j.j_months_fa[j.month - 1]} {j.year}"


def gregorian_to_jalali(d: date):
    return jdatetime.date.fromgregorian(date=d)


def jalali_str_for(d: date):
    j = gregorian_to_jalali(d)
    weekday = WEEKDAYS_FA[j.weekday()]
    return f"{weekday}، {j.day} {j.j_months_fa[j.month - 1]} {j.year}"
