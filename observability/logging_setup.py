"""
Setup Python logging dengan JSON formatter untuk GCP Cloud Logging.
Menyediakan fungsi konfigurasi logger dan helper untuk membuat
logger per modul dengan format terstruktur yang konsisten.
"""

import json
import logging
import sys
from datetime import datetime, timezone


# Field bawaan LogRecord yang tidak perlu diulang di payload JSON.
_STANDARD_LOG_FIELDS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
    "taskName",
})


class _JsonFormatter(logging.Formatter):
    """Formatter yang mengubah log record menjadi JSON satu baris.

    Menghasilkan structured log yang bisa di-parse dan di-filter
    per field secara independen di GCP Cloud Logging console.
    """
    def format(self, record: logging.LogRecord) -> str:
        """Memformat log record menjadi JSON string.

        Args:
            record: Log record dari Python logging.

        Returns:
            JSON string satu baris dengan field standar.
        """
        # Bangun payload standar yang selalu ada di setiap log entry.
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Tambahkan detail error hanya untuk log level ERROR ke atas.
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
            payload["error_detail"] = self.formatException(record.exc_info)

        # Sertakan field tambahan dari extra={} -- skip field bawaan LogRecord dan yang sudah ada di payload.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_FIELDS and key not in payload:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Mengkonfigurasi root logger dengan JSON formatter ke stdout.

    Dipanggil sekali saat aplikasi startup di api/main.py sebelum
    request pertama masuk. Semua logger yang dibuat setelah ini
    otomatis mewarisi konfigurasi ini.

    Args:
        level: Level logging minimum, default INFO.
    """
    # Arahkan semua log ke stdout agar ditangkap Cloud Run secara otomatis.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Hapus handler lama agar tidak ada duplikasi log saat setup dipanggil ulang.
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Mengembalikan logger dengan nama modul untuk dipakai per file.

    Args:
        name: Nama logger, konvensinya __name__ dari modul pemanggil.

    Returns:
        Logger instance siap dipakai.
    """
    return logging.getLogger(name)