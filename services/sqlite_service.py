"""
Lapisan koneksi read-only ke SQLite olist.db.
Menyediakan fungsi eksekusi query terhadap order_summary dan item_detail,
dipakai sql_tool. Koneksi dibuka dengan mode=ro sehingga operasi tulis
ditolak di level engine, ditambah validasi statement sebagai lapis kedua.
"""

import sqlite3

from config import DB_URI


# Kata kunci awal statement yang ditolak sebagai lapis kedua, selain guardrail utama mode=ro di level koneksi
_FORBIDDEN_STATEMENTS = {"DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"}


def execute_query(query: str) -> list[dict]:
    """Mengeksekusi query SQL terhadap database read-only dan mengembalikan hasilnya.
    
    Args:
        query: Query SQL yang akan dieksekusi, harus berupa SELECT.

    Returns:
        List baris hasil query, setiap baris berupa dict dengan key
        sesuai nama kolom pada hasil query.

    Raises:
        ValueError: Jika query diawali kata kunci yang termasuk operasi tulis.
        sqlite3.OperationalError: Jika query tidak valid secara sintaks,
            atau ditolak koneksi read-only karena alasan lain.
    """
    # Cek kata pertama saja agar tidak salah menolak SELECT yang kebetulan
    # menyebut kata ini di nilai kolom, misalnya teks ulasan.
    first_word = query.strip().split()[0].upper()
    if first_word in _FORBIDDEN_STATEMENTS:
        raise ValueError(f"Statement {first_word} tidak diizinkan, hanya SELECT yang diperbolehkan.")
    
    connection = sqlite3.connect(DB_URI, uri=True)
    connection.row_factory = sqlite3.Row

    try:
        cursor = connection.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()