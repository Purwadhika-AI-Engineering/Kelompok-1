"""
Schema Pydantic untuk request dan response endpont FastAPI.
Mendefinisikan kontrak data antara Streamlit dan backend LangGraph.
"""

from typing import Any, Literal

from pydantic import BaseModel


class InvestigateRequest(BaseModel):
    """Schema request untuk endpoint /investigate.
    
    Args:
        user_question: Pertanyaan pengguna dalam bahasa natural.
        conversation_history: Riwayat percakapan room aktif, list kosong jika pertanyaan pertama.
    """

    user_question: str
    conversation_history: list[dict[str, Any]]


class ProgressEvent(BaseModel):
    """Schema event progress yang dikirim setiap node tool selesai.
    
    Dikonsumsi Streamlit untuk mengupdate Loading State secara real-time.

    Args:
        type: Selalu bernilai progress untuk membedakan dari event final.
        step_name: Nama teknis node yang baru selesai, dipetakan ke label UI oleh Streamlit.
        status: Status node saat ini.
        iteration: Nomor iterasi ReAct saat ini.
    """

    type: Literal["progress"] = "progress"
    step_name: Literal["sql_tool", "rag_tool", "insight_agent"]
    status: Literal["done"]
    iteration: int


class TraceStep(BaseModel):
    """Satu langkah investigasi dalam response final, dipakai Streamlit untuk View Sources.
    
    Args:
        iteration: Nomor iterasi langkah ini.
        tool_called: Tool yang dipanggil pada langkah ini.
        tool_input: Kebutuhan data yang dikirim ke tool.
        query_used: Query SQL yang dieksekusi, kosong jika langkah ini adalah rag_tool.
        filters_appllied: Filter metadata yang diterapkan, kosong jika langkah ini adalah sql_tool.
        doc_count_retrieved: Jumlah dokumen relevan, nol jika langkah ini adalah sql_tool.
        """
    
    iteration: int
    tool_called: str
    tool_input: str
    query_used: str
    filters_applied: dict[str, Any]
    doc_count_retrieved: int


class TermTranslationResponse(BaseModel):
    """Satu pasangan istilah relatif dan definisi konkretnya dalam response final.
    
    Args:
        term: Istilah relatif dari pertanyaan pengguna.
        definition: Definisi konkret yang dipakai dalam investigasi.
    """
    term: str
    definition: str


class FinalEvent(BaseModel):
    """Schema event final yang dikirim sebagai event terakhir di akhir stream.
    
    Dikonsumsi Streamlit untuk merender jawaban utama dan View Sources.

    Args:
        type: Selalu bernilai final untuk membedakan dari event progress.
        final_answer: Teks jawaban dari Insight Agent atau pertanyaan klarifikasi.
        investigation_trace: Seluruh langkah investigasi untuk View Sources.
        term_translations: Seluruh istilah relatif yang diterjemahkan untuk bagian Definitions.
    """
    type: Literal["final"] = "final"
    final_answer: str
    investigation_trace: list[TraceStep]
    term_translations: list[TermTranslationResponse]