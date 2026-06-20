"""
Lapisan koneksi ke Qdrant Cloud.
Menyediakan fungsi pencarian semantik dengan filter metadata opsional
terhadap koleksi olist_reviews, dipakai rag_tool.
"""

import os

from qdrant_client import QdrantClient
from qdrant_client.models import Condition, FieldCondition, Filter, MatchValue, Range

from config import QDRANT_COLLECTION_NAME, TOP_K


# Satu instance client yang dipakai ulang sepanjang lifecycle aplikasi.
_client = QdrantClient(
    url=os.environ["QDRANT_URL"],
    api_key=os.environ["QDRANT_API_KEY"]
)

# review_score data Olist hanya bernilai 1 sampai 5.
_REVIEW_SCORE_BOUNDS = (1, 5)


def search_reviews(query_vector: list[float], filters: dict | None = None, top_k: int = TOP_K) -> list[dict]:
    """Mencari ulasan yang relevan secara semantik, dengan filter metadata opsional.
    
    Args:
        query_vector: Vector embedding hasil embed_text terhadap query pengguna.
        filters: Filter metadata, digabung dengan kondisi AND. Value tunggal (str/int/bool) untuk exact match,
            atau dict berisi gte/lte/gt/lt untuk range pada field numerik.
            Contoh: {"product_category": "electronics", "review_score": {"gte": 1, "lte": 2}}.
            None jika tidak perlu filter.
        top_k: Jumlah dokumen maksimum yang diambil.

    Returns:
        List dokumen ulasan yang lolos pencarian, setiap dokumen berupa dict
        berisi payload (teks ulasan dan metadata) beserta skor similarity.
    """
    qdrant_filter = _build_filter(filters) if filters else None

    response = _client.query_points(
        collection_name=QDRANT_COLLECTION_NAME,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=top_k
    )
    return [{"payload": point.payload, "score": point.score} for point in response.points]


def _build_filter(filters: dict) -> Filter:
    """Mengonversi dict filter sederhana menjadi objek Filter Qdrant.
    
    Setiap pasangan key-value adalah exact match, kecuali value berupa dict
    dengan key gte/lte/gt/lt yang diinterpretasikan sebagai range numerik.
    Seluruh kondisi digabung dengan AND. Filter review_score divalidasi
    terhadap batas domain data aktual sebelum dikirim ke Qdrant.

    Args:
        filters: Filter metadata, lihat docstring search_reviews untuk format.

    Returns:
        Objek Filter Qdrant siap dipakai sebagai query_filter.

    Raises:
        ValueError: Jika dict range berisi key selain gte/lte/gt/lt, atau
            filter review_score di luar batas data aktual.
    """
    range_keys = {"gte", "lte", "gt", "lt"}
    conditions: list[Condition] = []

    for key, value in filters.items():
        if isinstance(value, dict):
            unknown_keys = set(value.keys()) - range_keys

            if unknown_keys:
                raise ValueError(
                    f"Key range tidak dikenali untuk filter '{key}': {unknown_keys}. "
                    f"Hanya {range_keys} yang didukung."
                )
            
            if key == "review_score":
                _validate_review_score(*value.values())
            conditions.append(FieldCondition(key=key, range=Range(**value)))

        else:
            if key == "review_score":
                _validate_review_score(value)
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

    return Filter(must=conditions)


def _validate_review_score(*values) -> None:
    """Memvalidasi nilai review_score terhadap batas data aktual.
    
    Mencegah filter dengan nilai yang tidak mungkin ada di data, contoh
    review_score 10, terkirim ke Qdrant. Tanpa ini, filter semacam itu
    akan menghasilkan pencarian kosong yang bisa salah disimpulkan
    rag_tool sebagai tidak ada keluhan terkait, padahal akar masalahnya
    filter yang keliru.
    
    
    Args:
        *values: Satu atau lebih nilai review_score untuk dicek.
        
    Raises:
        ValueError: Jika ada nilai di luar 1 sampai 5.
    """
    lower, upper = _REVIEW_SCORE_BOUNDS
    invalid = [v for v in values if not isinstance(v, (int, float)) or not (lower <= v <= upper)]
    if invalid:
        raise ValueError(
            f"Nilai review_score di luar batas data aktual ({lower} sampai {upper}): {invalid}."
        )