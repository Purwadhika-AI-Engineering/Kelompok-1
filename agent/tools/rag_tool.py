"""
Agent rag_tool untuk Olist Insight Assistant.
Menerima kebutuhan dari Supervisor, mengekstrak filter via LLM (Call 1),
mengambil dokumen dari Qdrant, lalu mererank dan merangkum via LLM (Call 2).
"""

from typing import Optional

from pydantic import BaseModel, Field

from agent.prompts.rag_prompt import RAG_FILTER_PROMPT, RAG_SUMMARIZE_PROMPT
from agent.state import RagToolOutput, ToolRequest
from config import RAG_TOOL_MODEL, TOP_K
from services.embedding_service import embed_text
from services.llm_service import call_structured
from services.qdrant_service import search_reviews


class _RagFilterOutput(BaseModel):
    """Schema internal untuk Call 1: ekstraksi filter metadata dari kebutuhan investigasi.

    Args:
        filters_applied: Filter metadata yang diekstrak, siap dikirim ke Qdrant.
        error: Error jika kebutuhan tidak bisa diproses sama sekali.
    """

    filters_applied: dict = Field(
        default_factory=dict,
        description=(
            "Filter metadata yang diekstrak dari kebutuhan investigasi, "
            "siap dipakai sebagai filter pencarian Qdrant. "
            "Dict kosong jika tidak ada kondisi filter yang relevan."
        ),
    )
    error: Optional[str] = Field(
        default=None,
        description=(
            "Pesan error jika kebutuhan tidak bisa diproses sama sekali. "
            "Kosongkan jika filter berhasil diekstrak, termasuk jika hasilnya dict kosong."
        ),
    )


class _RagSummaryOutput(BaseModel):
    """Schema internal untuk Call 2: reranking dan summarization dokumen.

    Args:
        summary: Rangkuman tema dari dokumen yang lolos reranking.
        doc_count_retrieved: Jumlah dokumen yang lolos reranking.
        error: Error jika tidak ada dokumen relevan setelah reranking.
    """

    summary: str = Field(
        default="",
        description=(
            "Rangkuman tema dominan dari dokumen yang lolos reranking. "
            "Kosongkan jika tidak ada dokumen yang relevan."
        ),
    )
    doc_count_retrieved: int = Field(
        default=0,
        description="Jumlah dokumen yang lolos reranking dan dipakai untuk rangkuman.",
    )
    error: Optional[str] = Field(
        default=None,
        description=(
            "Pesan error jika tidak ada dokumen relevan setelah reranking. "
            "Kosongkan jika rangkuman berhasil dihasilkan."
        ),
    )


def run_rag_tool(tool_request: ToolRequest) -> RagToolOutput:
    """Mencari ulasan relevan dan merangkum tema dominannya.

    Args:
        tool_request: Permintaan dari Supervisor berisi kebutuhan pencarian
            dalam bahasa natural yang sudah menyertakan kriteria konkret.

    Returns:
        RagToolOutput dengan rangkuman tema, jumlah dokumen, filter yang
        diterapkan, dan error jika ada kegagalan di tahap mana pun.
    """
    # Call 1: LLM mengekstrak filter metadata dari kebutuhan data.
    filter_output = call_structured(
        model_name=RAG_TOOL_MODEL,
        system_prompt=RAG_FILTER_PROMPT,
        user_message=tool_request.data_request,
        output_schema=_RagFilterOutput,
    )

    # Call 1 gagal total, kebutuhan tidak bisa diproses sama sekali.
    if filter_output.error:
        return RagToolOutput(
            summary="",
            filters_applied={},
            error=filter_output.error,
        )

    # Embed query dan ambil dokumen dari Qdrant, keduanya bisa gagal karena layanan eksternal.
    try:
        query_vector = embed_text(tool_request.data_request)
        raw_docs = search_reviews(
            query_vector=query_vector,
            filters=filter_output.filters_applied if filter_output.filters_applied else None,
            top_k=TOP_K,
        )
    except Exception as e:
        return RagToolOutput(
            summary="",
            filters_applied=filter_output.filters_applied,
            error=f"Retrieval gagal: {str(e)}",
        )

    # Tidak ada dokumen yang diambil, tidak perlu Call 2.
    if not raw_docs:
        return RagToolOutput(
            summary="",
            doc_count_retrieved=0,
            filters_applied=filter_output.filters_applied,
            error="Tidak ada dokumen yang ditemukan dengan filter dan query yang diberikan.",
        )

    # Bangun konteks untuk Call 2: kebutuhan investigasi + seluruh dokumen yang diambil.
    docs_context = _format_docs_for_llm(raw_docs)
    user_message = (
        f"KEBUTUHAN INVESTIGASI\n{tool_request.data_request}\n\n"
        f"DOKUMEN YANG DIAMBIL ({len(raw_docs)} dokumen)\n{docs_context}"
    )

    # Call 2: LLM mererank dan merangkum dokumen yang diambil.
    summary_output = call_structured(
        model_name=RAG_TOOL_MODEL,
        system_prompt=RAG_SUMMARIZE_PROMPT,
        user_message=user_message,
        output_schema=_RagSummaryOutput,
    )

    # Gabungkan filters_applied dari Call 1 dengan summary dan doc_count dari Call 2.
    return RagToolOutput(
        summary=summary_output.summary,
        doc_count_retrieved=summary_output.doc_count_retrieved,
        filters_applied=filter_output.filters_applied,
        error=summary_output.error,
    )


def _format_docs_for_llm(docs: list[dict]) -> str:
    """Memformat dokumen hasil retrieval menjadi teks terstruktur untuk LLM Call 2.

    Args:
        docs: List dokumen dari search_reviews, setiap elemen berisi
            payload (teks ulasan dan metadata) dan skor similarity.

    Returns:
        Teks terstruktur dengan nomor urut dan seluruh field payload tiap dokumen.
    """
    lines = []
    for i, doc in enumerate(docs, start=1):
        payload = doc.get("payload", {})
        score = doc.get("score", 0)
        lines.append(f"[Dokumen {i}] (similarity: {score:.3f})")
        for key, value in payload.items():
            lines.append(f"  {key}: {value}")
        lines.append("")
    return "\n".join(lines)