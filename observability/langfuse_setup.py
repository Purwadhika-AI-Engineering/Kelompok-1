"""
Setup Langfuse callback handler untuk tracing investigasi.
Menyediakan fungsi untuk mendapatkan callback handler yang disisipkan
ke graph.streanm() agar setiap LLM call otomatis di-trace.
"""

from langfuse.langchain import CallbackHandler


def get_langfuse_handler() -> CallbackHandler:
    """Membuat instance CallbackHandler Langfuse untuk satu invocation graph.
    
    Satu handler per invocation agar setiap pertanyaan menghasilkan
    satu trace terpisah di dashboard Langfuse, bukan satu trace panjang
    yang menggabungkan semua pertanyaan dari semua room.
    Credentials dibaca otomatis dari environment variable LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY, dan LANGFUSE_HOST.

    Returns:
        CallbackHandler siap disisipkan ke config graph.stream().
    """
    # Credentials diambil otomatis dari environment variable oleh langfuse v4.
    return CallbackHandler()