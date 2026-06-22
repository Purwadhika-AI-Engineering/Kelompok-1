"""
Lapisan koneksi ke OpenAI Embedding API.
Menyediakan fungsi untuk mengubah teks menjadi vector embedding,
dipakai rag_tool untuk meng-embed query pengguna sebelum pencarian di Qdrant.
"""

from openai import OpenAI

from config import EMBEDDING_MODEL, VECTOR_DIMENSION

# Satu instance client yang dipakai ulang sepanjang lifecycle aplikasi
_client = OpenAI()


def embed_text(text: str) -> list[float]:
    """Mengubah teks menjadi vector embedding.
    
    Model yang dipakai wajib identik dengan model yang dipakai saat ingestion data ke Qdrant.
    Ketidakcocokan model atau dimensi menghasilkan pencarian similarity yang tidak valid
    secara senyap.

    Args:
        text: Teks yang akan diubah menjadi vector, biasanya query pengguna yang sudah diproses Supervisor.
    
    Returns:
        Vector embedding dengan dimensi sesuai VECTOR_DIMENSION.

    Raises:
        ValueError: Jika dimensi vector yang dihasilkan API tidak sesuai
            dengan VECTOR_DIMENSION yang dikonfigurasi.
    """
    response = _client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text
    )
    vector = response.data[0].embedding

    # Validasi eksplisit agar gagal ketidakcocokan dimensi dapat terlihat jelas saat runtime
    if len(vector) != VECTOR_DIMENSION:
        raise ValueError(
            f"Dimensi embedding tidak sesuai. Diharapkan {VECTOR_DIMENSION}, didapat {len(vector)}."
        )
    
    return vector