# -*- coding: utf-8 -*-
"""پخش فایل‌های صوتی (اذان و صداهای دلخواه) با استفاده از pygame.mixer"""

import threading

_lock = threading.Lock()
_initialized = False


def _ensure_init():
    global _initialized
    if not _initialized:
        import pygame
        pygame.mixer.init()
        _initialized = True


def get_duration_seconds(file_path: str):
    """طول زمانی (ثانیه) یک فایل صوتی را برمی‌گرداند، یا None در صورت عدم امکان تشخیص."""
    if not file_path:
        return None
    try:
        from mutagen import File as MutagenFile
        mf = MutagenFile(file_path)
        if mf is not None and mf.info is not None and mf.info.length:
            return float(mf.info.length)
    except Exception:
        pass
    return None



def play(file_path: str, volume: float = 0.8, blocking: bool = False, on_finish=None):
    """پخش یک فایل صوتی. اگر blocking=False باشد در یک ترد جداگانه پخش می‌شود."""
    if not file_path:
        return

    def _run():
        import pygame
        with _lock:
            _ensure_init()
            try:
                pygame.mixer.music.load(file_path)
                pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
                pygame.mixer.music.play()
            except Exception as e:
                print("خطا در پخش فایل صوتی:", e)
                if on_finish:
                    on_finish()
                return
        if blocking:
            import time
            while pygame.mixer.music.get_busy():
                time.sleep(0.2)
            if on_finish:
                on_finish()
        else:
            if on_finish:
                # نظارت غیرمسدودکننده بر پایان پخش
                def _watch():
                    import time
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.3)
                    on_finish()
                threading.Thread(target=_watch, daemon=True).start()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def stop():
    try:
        import pygame
        if _initialized:
            pygame.mixer.music.stop()
    except Exception:
        pass


def is_playing() -> bool:
    try:
        import pygame
        return _initialized and pygame.mixer.music.get_busy()
    except Exception:
        return False
