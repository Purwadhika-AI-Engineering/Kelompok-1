"""
Definisi state graph dan class Pydantic pendukung untuk Olist Insight Assistant.
AgentState adalah satu-satunya sumber kebenaran yang dibaca dan ditulis setiap node.
"""

import operator
from typing import Annotated, Literal, Optional, TypedDict, Union

from pydantic import BaseModel, Field


class SqlToolOutput(BaseModel):
    """Hasil terstruktur dari eksekusi sql_tool.

    Args:
        rows: Baris hasil query.
        query_used: Query SQL lengkap yang dieksekusi.
        error: Pesan error jika query gagal, None jika sukses.
    """
    rows: list[dict] = Field(
        default_factory=list,
        description=(
            "Hasil baris dari eksekusi query SQL. Setiap elemen adalah satu "
            "baris, berupa dict dengan key sesuai nama kolom pada query. "
            "Kosongkan jika query gagal atau kebutuhan tidak bisa dipenuhi."
        )
    )
    query_used: str = Field(
        description=(
            "Query SQL lengkap yang dieksekusi, ditulis persis seperti yang "
            "dijalankan tanpa diringkas atau diubah, untuk transparansi. "
            "Eksekusi dilakukan oleh sistem di luar LLM, bukan oleh LLM "
            "sendiri. Kosongkan jika tidak ada query yang bisa dihasilkan."
        )
    )
    error: Optional[str] = Field(
        default=None,
        description=(
            "Pesan error jika query gagal dieksekusi atau kebutuhan data "
            "tidak bisa dipenuhi skema yang ada. Kosongkan jika sukses."
        )
    )


class RagToolOutput(BaseModel):
    """Hasil terstruktur dari eksekusi rag_tool.
    
    Args:
        summary: Rangkuman tema dari ulasan yang relevan.
        doc_count_retrieved: Jumlah dokumen yang lolos filter dan reranking.
        filters_applied: Filter metadata yang diterapkan pada pencarian.
    """
    summary: str = Field(
        description=(
            "Rangkuman tema dominan dari ulasan yang relevan, berdasarkan dokumen "
            "yang lolos filter metadata dan reranking."
        )
    )
    doc_count_retrieved: int = Field(
        description=(
            "Jumlah dokumen ulasan yang lolos filter dan dinilai relevan setelah reranking. "
            "Dipakai Insight Agent untuk menilai kekuatan sampel sebelum membuat klaim."
        )
    )
    filters_applied: dict = Field(
        description=(
            "Filter metadata yang diterapkan pada pencarian, key-value sesuai field metadata "
            "yang tersedia di koleksi Qdrant. Hanya sertakan key yang benar-benar dipakai."
        )
    )
    

class InvestigationStep(BaseModel):
    """Satu siklus Reason-Act-Observe dalam ReAct loop Supervisor.

    Args:
        iteration: Nomor urut iterasi ReAct.
        reasoning: Alasan Supervisor memilih langkah ini.
        tool_called: Tool yang dipanggil pada langkah ini.
        tool_input: Kebutuhan data yang dikirim ke tool.
        tool_output: Hasil terstruktur dari tool, tipe mengikuti tool yang dipanggil.
    """
    iteration: int = Field(
        description="Nomor urut iterasi ReAct, dimulai dari 1."
        )
    reasoning: str= Field(
        description=(
        "Penjelasan Supervisor tentang langkah yang diambil pada iterasi ini dan alasannya. "
        "Akan dibaca ulang oleh Insight Agent saat sintesis, jadi tulis dengan jelas, bukan sekedar catatan internal."
        )
    )
    tool_called: Literal["sql_tool", "rag_tool"] = Field(
        description="Tool yang dipanggil pada langkah ini"
    )
    tool_input: str = Field(
        description="Kebutuhan data yang dikirim ke tool, sama dengan isi ToolRequest.data_request pada langkah ini."
    )
    tool_output: Union[SqlToolOutput, RagToolOutput] = Field(
        description="Hasil terstruktur yang dikembalikan tool setelah eksekusi, menjadi observasi untuk iterasi berikutnya."
    )


class ToolRequest(BaseModel):
    """Permintaan terstruktur dari Supervisor ke tool yang akan dipanggil.

    Args:
        tool_name: Nama tool yang akan dipanggil.
        data_request: Kebutuhan data dalam bahasa natural.
    """
    tool_name: Literal["sql_tool", "rag_tool"] = Field(
        description="Tool yang akan dipanggil untuk memenuhi kebutuhan investigasi."
    )
    data_request: str = Field(
        description=(
            "Kebutuhan data spesifik untuk tool yang dipilih, dirumuskan berdasarkan konteks investigasi sejauh ini "
            "dan sudah menyertakan hasil penerjemahan istilah relatif jika relevan."
            "Untuk sql_tool: sebutkan metrik, agregasi, dan filter secara eksplisit, "
            "contoh: hitung rata-rata review_score per kategori produk pada Q3 2018. "
            "Untuk rag_tool: sebutkan topik atau jenis keluhan yang dicari secara semantik beserta filter metadata jika relevan, "
            "contoh: review yang mengeluhkan kemasan rusak pada kategori elektronik dengan review_score rendah."
        )
    )


class TermTranslation(BaseModel):
    """Catatan penerjemahan istilah relatif menjadi kriteria data konkret.

    Args:
        term: Istilah relatif dari pertanyaan pengguna.
        definition: Definisi konkret yang dipakai dalam investigasi.
    """
    term: str = Field(description="Istilah relatif yang muncul dalam pertanyaan pengguna, misalnya: rating rendah.")
    definition: str = Field(
        description=(
            "Definisi konkret yang dipakai dalam investigasi ini, misalnya: review_score 1 sampai 2. "
            "Untuk istilah tanpa definisi baku seperti harga mahal, definisi ini berupa ambang yang ditentukan dari "
            "distribusi data aktual, bukan angka tetap."
        )
    )


class SupervisorOutput(BaseModel):
    """Schema stuctured output untuk satu pemanggilan LLM Supervisor.
    
    Hasil ini dibaca node Supervisor lalu di-merge ke AgentState,
    bukan menggantikan seluruh state.

    Args:
        action: Keputusan langkah berikutnya.
        reasoning: Alasan di balik keputusan action.
        tool_request: Wajib diisi jika action adalah tool_call.
        clarification_question: Wajib diisi jika action adalah clarify.
        term_translations: Penerjemahan istilah relatif baru pada iterasi ini, jika ada.
    """
    action: Literal["tool_call", "finish", "clarify"] = Field(
        description=(
            "Keputusan langkah berikutnya: tool_call untuk memanggil tool, "
            "finish jika bukti sudah cukup untuk sintesis, clarify jika pertanyaan terlalu ambigu."
        )
    )
    reasoning: str = Field(
        description="Alasan di balik keputusan action ini."
    )
    tool_request: Optional[ToolRequest] = Field(
        default=None,
        description=(
            "Wajib diisi jika action=tool_call, kosong jika action lain."
        )
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description=(
            "Wajib diisi jika action=clarify, kosongkan jika action lain."
        )
    )
    term_translations: list[TermTranslation] = Field(
        default_factory=list,
        description=(
            "Penerjemahan istilah relatif baru yang diputuskan pada iterasi ini saja, "
            "misalnya saat merumuskan tool_request dan menemukan istilah seperti 'rating rendah' "
            "atau 'bulan lalu' yang perlu diterjemahkan menjadi kriteria data konkret. "
            "Kosongkan list ini (list kosong) jika tidak ada istilah relatif baru yang perlu "
            "diterjemahkan pada langkah ini. Jangan ulangi istilah yang sudah diterjemahkan "
            "pada iterasi sebelumnya."
        )
    )


class AgentState(TypedDict):
    """State graph yang dibawa LangGraph sepanjang satu invocation.

    Semua node membaca dan menulis ke state ini.
    investigation_trace dan term_translations menggunakan operator.add
    sehingga setiap write append, bukan overwrite.

    Catatan inisialisasi: TypedDict tidak memiliki mekanisme default value.
    Semua field, termasuk yang bertipe Optional, harus diisi eksplisit
    (None untuk field tunggal, list kosong untuk field beranotasi operator.add)
    saat state pertama kali dibuat sebelum invocation dimulai.
    Gunakan build_initial_state untuk membuat state awal yang valid,
    jangan membuat dict secara manual.
    """
    user_question: str
    conversation_history: list[dict]
    investigation_trace: Annotated[list[InvestigationStep], operator.add]
    term_translations: Annotated[list[TermTranslation], operator.add]
    iteration_count: int
    action: Optional[Literal["tool_call", "finish", "clarify"]]
    tool_request: Optional[ToolRequest]
    clarification_question: Optional[str]
    final_answer: Optional[str]


def build_initial_state(user_question: str, conversation_history: list[dict]) -> AgentState:
    """Membuat AgentState kosong yang valid untuk memulai satu invocation baru.
    
    Mengisi seluruh field secara eksplisit, termasuk field Optional karena TypedDict
    tidak memiliki default value otomatis. Tanpa fungsi ini, akses ke field yang
    belum pernah ditulis node manapun akan menghasilkan KeyError, bukan None.

    Args:
        user_question: Pertanyaan pengguna untuk invocation ini.
        conversation_history: Riwayat percakapan sebelumnya, list kosong jika baru.

    Returns:
        AgentState dengan seluruh field terisi nilai awal yang valid.
    """
    return {
        "user_question": user_question,
        "conversation_history": conversation_history,
        "investigation_trace": [],
        "term_translations": [],
        "iteration_count": 0,
        "action": None,
        "tool_request": None,
        "clarification_question": None,
        "final_answer": None
    }
