"""DETAS bellek ve dosya log servisi."""

import threading
import time
from pathlib import Path

try:
    from config import LOG_ENCODING, LOG_FILE, LOG_MAX_ITEMS, LOG_TIME_FORMAT
except ImportError:
    BASE_DIR = Path(__file__).resolve().parent.parent
    LOG_FILE = BASE_DIR / "logs" / "detas.log"
    LOG_MAX_ITEMS = 30
    LOG_TIME_FORMAT = "%H:%M:%S"
    LOG_ENCODING = "utf-8"


logs = []
_log_lock = threading.Lock()


def _write_log_file(log_line):
    """Log satirini UTF-8 olarak dosyaya ekler."""
    try:
        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with log_path.open("a", encoding=LOG_ENCODING) as log_file:
            log_file.write(log_line + "\n")
    except Exception as exc:
        # Dosya logu basarisiz olsa bile uygulama calismaya devam eder.
        try:
            print(f"Log dosyasi yazma hatasi: {exc}")
        except Exception:
            pass


def add_log(message, write_to_file=True):
    """Mesaji terminale, bellege ve istege bagli olarak dosyaya yazar."""
    try:
        timestamp = time.strftime(LOG_TIME_FORMAT)
        log_line = f"[{timestamp}] {str(message)}"

        with _log_lock:
            logs.insert(0, log_line)
            del logs[LOG_MAX_ITEMS:]

        try:
            print(log_line)
        except Exception:
            pass

        if write_to_file:
            _write_log_file(log_line)

        return log_line
    except Exception:
        # Loglama hatasi ana sistemi durdurmamali.
        return None


def get_logs():
    """Panel API'si icin son loglarin guvenli bir kopyasini dondurur."""
    try:
        with _log_lock:
            return list(logs)
    except Exception:
        return []
