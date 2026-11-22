# -*- coding: utf-8 -*-
"""فعال/غیرفعال‌سازی اجرای خودکار برنامه هنگام روشن شدن ویندوز
(با افزودن/حذف کلید در HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
"""

import sys
import os

APP_NAME = "AzanGoo"


def _is_windows():
    return sys.platform.startswith("win")


def _get_exe_command():
    """دستوری که باید هنگام استارتاپ اجرا شود؛ برای exe نهایی یا اجرای از سورس پایتون"""
    if getattr(sys, "frozen", False):
        # اجرا به صورت exe ساخته‌شده با PyInstaller
        return f'"{sys.executable}"'
    else:
        # اجرا از سورس پایتون
        script = os.path.abspath(sys.argv[0])
        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        return f'"{pythonw}" "{script}"'


def is_enabled() -> bool:
    if not _is_windows():
        return False
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ,
        )
        try:
            winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def set_enabled(enabled: bool):
    if not _is_windows():
        return False, "اجرای خودکار فقط در ویندوز پشتیبانی می‌شود."
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _get_exe_command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True, ""
    except Exception as e:
        return False, str(e)
