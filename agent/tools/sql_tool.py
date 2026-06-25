"""
Agent sql_tool untuk Olist Insight Assistant.
Menerima kebutuhan data dari Supervisor dalam bahasa natural, menghasilkan
query SQL via LLM, mengeksekusinya terhadap database read-only, dan
mengembalikan hasil terstruktur beserta query yang dipakai untuk transparansi.
"""

from typing import Optional

from pydantic import BaseModel, Field

from agent.prompts.sql_prompt import SQL_PROMPT
from agent.state import AgentState, InvestigationStep, SqlToolOutput, ToolRequest
from config import SQL_TOOL_MODEL
from services.llm_service import call_structured
from services.sqlite_service import execute_query


# Batas maksimum baris yang disimpan ke state sebagai safety net.
_ROW_CAP = 100


class _SqlQueryPlan(BaseModel):
    """Schema internal untuk output LLM sql_tool.
    
    LLM hanya bertugas menghasilkan query SQL yang valid terhadap skema
    yang diberikan di system prompt. Eksekusi dilakukan Python setelah
    output ini diterima. Dipisah dari SqlToolOutput agar LLM tidak
    mencoba mengisi field rows yang bukan tugasnya.

    Args:
        query_used: Query SQL yang akan dieksekusi sistem.
        error: Error jika permintaan tidak bisa dipenuhi secara sah.
    """
    query_used: str = Field(
        default="",
        description=(
            "Query SQL lengkap yang siap dieksekusi, ditulis persis seperti "
            "yang seharusnya dijalankan. Kosongkan jika permintaan tidak bisa "
            "dipenuhi secara sah dengan skema yang tersedia."
        )
    )
    error: Optional[str] = Field(
        default=None,
        description=(
            "Pesan error jika permintaan tidak bisa dipenuhi secara sah, "
            "misalnya kolom tidak ada di skema atau operasi selain SELECT diminta. "
            "Kosongkan jika query berhasil dihasilkan."
        )
    )


def run_sql_tool(tool_request: ToolRequest) -> SqlToolOutput:
    """Menerjemahkan kebutuhan data menjadi SQL, mengeksekusi, dan mengembalikan hasil.
    
    Args:
        tool_request: Permintaan dari Supervisor berisi kebutuhan data
            dalam bahasa natural yang sudah menyertakan kriteria konkret.

    Returns:
        SqlToolOutput dengan rows hasil eksekusi, query yang dipakai,
        dan error jika ada kegagalan di tahap manapun.
    """
    # LLM menerjemahkan kebutuhan data menjadi query SQL.
    query_plan = call_structured(
        model_name=SQL_TOOL_MODEL,
        system_prompt=SQL_PROMPT,
        user_message=tool_request.data_request,
        output_schema=_SqlQueryPlan
    )

    # LLM melaporkan error, tidak ada query yang bisa dieksekusi.
    if query_plan.error:
        return SqlToolOutput(
            query_used=query_plan.query_used,
            error=query_plan.error
        )
    
    # Guard: LLM tidak menghasilkan query dan tidak melaporkan error.
    if not query_plan.query_used.strip():
        return SqlToolOutput(
            query_used="",
            error="LLM tidak menghasilkan query. Kebutuhan data tidak bisa dipenuhi skema yang ada."
        )
    
    # Python mengeksekusi query ke database read-only.
    try:
        rows = execute_query(query_plan.query_used)

        # Potong baris yang masuk ke state sebagai last resort jika prompt tidak cukup.
        rows = rows[:_ROW_CAP]

        return SqlToolOutput(
            rows=rows,
            query_used=query_plan.query_used
        )
    
    except Exception as e:
        return SqlToolOutput(
            query_used=query_plan.query_used,
            error=f"Eksekusi query gagal: {str(e)}"
        )
    

def sql_tool_node(state: AgentState) -> dict:
    """Node LangGraph wrapper untuk sql_tool.

    Membaca tool_request dan current_reasoning dari state, menjalankan
    run_sql_tool, membangun InvestigationStep lengkap, dan mengembalikan
    update state dengan step baru di investigation_trace.

    Args:
        state: State graph saat ini berisi tool_request dan current_reasoning
            yang ditulis Supervisor pada iterasi sebelumnya.

    Returns:
        Dict update state: investigation_trace berisi satu InvestigationStep
        baru, dan current_reasoning direset ke None.

    Raises:
        ValueError: Jika tool_request atau current_reasoning tidak tersedia di state.
    """
    # Guard: kedua field wajib ada karena node ini hanya dipanggil saat action=tool_call.
    if state["tool_request"] is None or state["current_reasoning"] is None:
        raise ValueError("sql_tool_node dipanggil tanpa tool_request atau current_reasoning di state.")

    tool_request = state["tool_request"]
    reasoning = state["current_reasoning"]
    iteration = state["iteration_count"]

    # Jalankan logic sql_tool: generate query, eksekusi, return hasil.
    tool_output = run_sql_tool(tool_request)

    # Bangun satu siklus Reason-Act-Observe yang lengkap.
    step = InvestigationStep(
        iteration=iteration,
        reasoning=reasoning,
        tool_called="sql_tool",
        tool_input=tool_request.data_request,
        tool_output=tool_output,
    )

    # Reset current_reasoning setelah dikonsumsi agar tidak terbawa ke iterasi berikutnya.
    return {
        "investigation_trace": [step],
        "current_reasoning": None,
    }