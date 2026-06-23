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
        rows: Baris hasil query, diisi sistem setelah eksekusi.
        query_used: Query SQL lengkap yang dieksekusi.
        error: Pesan error jika query gagal, None jika sukses.
    """

    rows: list[dict] = Field(
        default_factory=list,
        description=(
            "Hasil baris dari eksekusi query_used terhadap database, diisi "
            "oleh sistem setelah query dijalankan, bukan oleh LLM. "
            "Setiap elemen adalah satu baris berupa dict dengan key sesuai "
            "nama kolom pada query. List kosong jika query gagal, kebutuhan "
            "tidak bisa dipenuhi, atau query valid tapi tidak ada baris yang "
            "dikembalikan."
        ),
    )
    query_used: str = Field(
        description=(
            "Query SQL lengkap yang akan dieksekusi, ditulis persis seperti "
            "yang akan dijalankan tanpa diringkas atau diubah. Eksekusi "
            "dilakukan oleh sistem di luar LLM, bukan oleh LLM sendiri. "
            "String kosong jika kebutuhan tidak bisa diwujudkan menjadi "
            "query yang valid terhadap skema yang tersedia."
        ),
    )
    error: Optional[str] = Field(
        default=None,
        description=(
            "Pesan error jika query tidak bisa dihasilkan atau kebutuhan "
            "tidak bisa dipenuhi skema yang ada, misalnya permintaan operasi "
            "selain SELECT atau kolom yang tidak tersedia. None jika sukses."
        ),
    )


class RagToolOutput(BaseModel):
    """Hasil terstruktur dari eksekusi rag_tool.

    Args:
        summary: Rangkuman tema dari ulasan yang lolos penilaian relevansi.
        doc_count_retrieved: Jumlah dokumen yang lolos penilaian relevansi.
        filters_applied: Filter metadata yang diterapkan pada pencarian.
        error: Pesan error jika retrieval gagal, None jika sukses.
    """

    summary: str = Field(
        description=(
            "Rangkuman tema dominan dari ulasan yang lolos penilaian "
            "relevansi, dalam bahasa Indonesia. Bedakan tema dominan yang "
            "muncul di mayoritas ulasan dari penyebutan terisolasi yang "
            "hanya muncul di satu atau dua ulasan. Sertakan konteks jumlah "
            "dokumen yang dianalisis dan filter yang diterapkan di awal "
            "rangkuman agar Insight Agent memiliki konteks yang cukup. "
            "String kosong jika tidak ada dokumen relevan yang ditemukan."
        ),
    )
    doc_count_retrieved: int = Field(
        default=0,
        description=(
            "Jumlah dokumen ulasan yang lolos penilaian relevansi dan "
            "benar-benar dipakai untuk menyusun rangkuman. Ini adalah "
            "hitungan setelah penilaian relevansi, bukan jumlah total "
            "kandidat yang diambil dari Qdrant. Dipakai Insight Agent "
            "untuk menilai kekuatan sampel sebelum membuat klaim."
        ),
    )
    filters_applied: dict = Field(
        default_factory=dict,
        description=(
            "Filter metadata yang diterapkan pada pencarian Qdrant, "
            "key-value sesuai field metadata yang tersedia di koleksi. "
            "Nilai kategorikal berupa string, nilai numerik berupa range "
            "object dengan key gte dan atau lte, contoh: "
            "{'gte': 1, 'lte': 2}. Hanya sertakan key yang benar-benar "
            "diterapkan. Dict kosong jika tidak ada filter yang dipakai."
        ),
    )
    error: Optional[str] = Field(
        default=None,
        description=(
            "Pesan error jika retrieval gagal atau tidak ada dokumen "
            "relevan yang ditemukan setelah penilaian relevansi. "
            "None jika sukses."
        ),
    )


class InvestigationStep(BaseModel):
    """Satu siklus Reason-Act-Observe dalam ReAct loop Supervisor.

    Args:
        iteration: Nomor urut iterasi ReAct.
        reasoning: Reasoning Supervisor yang menjadi dasar langkah ini.
        tool_called: Tool yang dipanggil pada langkah ini.
        tool_input: Kebutuhan data yang dikirim ke tool.
        tool_output: Hasil terstruktur dari tool.
    """

    iteration: int = Field(
        description="Nomor urut iterasi ReAct, dimulai dari 1.",
    )
    reasoning: str = Field(
        description=(
            "Reasoning Supervisor yang menjadi dasar langkah ini, disalin "
            "dari SupervisorOutput.reasoning pada iterasi yang sama. Dibaca "
            "Insight Agent saat sintesis untuk memahami strategi dan logika "
            "investigasi, serta dibaca Supervisor pada iterasi berikutnya "
            "sebagai bagian dari konteks penuh investigasi."
        ),
    )
    tool_called: Literal["sql_tool", "rag_tool"] = Field(
        description=(
            "Tool yang dipanggil pada langkah ini, "
            "sesuai ToolRequest.tool_name pada iterasi yang sama."
        ),
    )
    tool_input: str = Field(
        description=(
            "Kebutuhan data yang dikirim ke tool, sama dengan isi "
            "ToolRequest.data_request pada langkah ini."
        ),
    )
    tool_output: Union[SqlToolOutput, RagToolOutput] = Field(
        description=(
            "Hasil terstruktur yang dikembalikan tool setelah eksekusi. "
            "Menjadi observasi Supervisor pada iterasi berikutnya dan "
            "bukti yang disintesis Insight Agent pada tahap akhir."
        ),
    )


class ToolRequest(BaseModel):
    """Permintaan terstruktur dari Supervisor ke tool yang akan dipanggil.

    Args:
        tool_name: Nama tool yang akan dipanggil.
        data_request: Kebutuhan data dalam bahasa natural.
    """

    tool_name: Literal["sql_tool", "rag_tool"] = Field(
        description="Tool yang akan dipanggil untuk memenuhi kebutuhan investigasi.",
    )
    data_request: str = Field(
        description=(
            "Kebutuhan data spesifik untuk tool yang dipilih, dirumuskan "
            "berdasarkan konteks investigasi sejauh ini dan sudah menyertakan "
            "hasil penerjemahan istilah relatif jika relevan. "
            "Untuk sql_tool: sebutkan metrik, agregasi, dan filter secara "
            "eksplisit, contoh: hitung rata-rata review_score per kategori "
            "produk pada Q3 2018. "
            "Untuk rag_tool: sebutkan topik atau jenis keluhan yang dicari "
            "secara semantik beserta filter metadata jika relevan, contoh: "
            "review yang mengeluhkan kemasan rusak pada kategori elektronik "
            "dengan review_score rendah."
        ),
    )


class TermTranslation(BaseModel):
    """Catatan penerjemahan istilah relatif menjadi kriteria data konkret.

    Args:
        term: Istilah relatif dari pertanyaan pengguna.
        definition: Definisi konkret yang dipakai dalam investigasi ini.
    """

    term: str = Field(
        description=(
            "Istilah relatif yang muncul dalam pertanyaan pengguna, "
            "misalnya: rating rendah, pengiriman lambat, harga mahal."
        ),
    )
    definition: str = Field(
        description=(
            "Definisi konkret yang dipakai dalam investigasi ini, misalnya: "
            "review_score 1 sampai 2. Untuk istilah tanpa ambang baku seperti "
            "harga mahal, definisi berupa ambang yang ditentukan dari distribusi "
            "kolom aktual lewat sql_tool, bukan angka tetap yang diasumsikan."
        ),
    )


class SupervisorOutput(BaseModel):
    """Schema structured output untuk satu pemanggilan LLM Supervisor.

    Hasil ini dibaca node Supervisor lalu di-merge ke AgentState,
    bukan menggantikan seluruh state.

    Args:
        action: Keputusan langkah berikutnya.
        reasoning: Alasan di balik keputusan action, dibaca Insight Agent saat sintesis.
        tool_request: Wajib diisi jika action adalah tool_call.
        clarification_question: Wajib diisi jika action adalah clarify.
        term_translations: Penerjemahan istilah relatif baru pada iterasi ini, jika ada.
    """

    action: Literal["tool_call", "finish", "clarify"] = Field(
        description=(
            "Keputusan langkah berikutnya: tool_call untuk memanggil tool, "
            "finish jika bukti sudah cukup untuk sintesis, clarify jika "
            "pertanyaan terlalu ambigu untuk diinvestigasi atau berada di "
            "luar domain Olist."
        ),
    )
    reasoning: str = Field(
        description=(
            "Alasan di balik keputusan action ini. Tulis secara jelas dan "
            "substantif karena reasoning ini akan disalin ke investigation_trace "
            "dan dibaca Insight Agent saat sintesis untuk memahami strategi "
            "dan logika investigasi, bukan sekadar catatan internal."
        ),
    )
    tool_request: Optional[ToolRequest] = Field(
        default=None,
        description=(
            "Wajib diisi jika action=tool_call, None jika action lain."
        ),
    )
    clarification_question: Optional[str] = Field(
        default=None,
        description=(
            "Wajib diisi jika action=clarify, None jika action lain. "
            "Satu pertanyaan klarifikasi dengan dua atau tiga pilihan konkret."
        ),
    )
    term_translations: list[TermTranslation] = Field(
        default_factory=list,
        description=(
            "Penerjemahan istilah relatif baru yang diputuskan pada iterasi "
            "ini saja, misalnya 'rating rendah' menjadi review_score 1 sampai 2, "
            "atau 'bulan lalu' menjadi periode bulan kalender sebelumnya. "
            "List kosong jika tidak ada istilah relatif baru pada langkah ini. "
            "Jangan ulangi istilah yang sudah diterjemahkan pada iterasi "
            "sebelumnya karena akan terakumulasi di state secara otomatis."
        ),
    )


class AgentState(TypedDict):
    """State graph yang dibawa LangGraph sepanjang satu invocation.

    Semua node membaca dan menulis ke state ini.
    investigation_trace dan term_translations menggunakan operator.add
    sehingga setiap write append, bukan overwrite.

    Catatan inisialisasi: TypedDict tidak memiliki mekanisme default value.
    Semua field, termasuk yang bertipe Optional, harus diisi eksplisit
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
    current_reasoning: Optional[str]
    clarification_question: Optional[str]
    final_answer: Optional[str]


def build_initial_state(
    user_question: str, conversation_history: list[dict]
) -> AgentState:
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
        "current_reasoning": None,
        "clarification_question": None,
        "final_answer": None,
    }