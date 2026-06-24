"""
Node Supervisor untuk Olist Insight Assistant.
Menjalankan satu langkah ReAct: membaca konteks investigasi, memanggil LLM
untuk menghasilkan keputusan terstruktur, dan menulis hasilnya ke state.
"""

import json

from agent.prompts.supervisor_prompt import SUPERVISOR_PROMPT
from agent.state import AgentState, SupervisorOutput
from config import MAX_ITERATIONS, SUPERVISOR_MODEL
from services.llm_service import call_structured


def run_supervisor(state: AgentState) -> dict:
    """Menjalankan satu iterasi ReAct Supervisor.
    
    Membaca state saat ini, membangun konteks investigasi lengkap,
    memanggil LLM untuk menghasilkan keputusan, dan mengembalikan
    update state. Jika batas iterasi tercapai, memaksa action finish.

    Args:
        state: State graph saat ini berisi seluruh konteks investigasi.

    Returns:
        Dict update state: action, current_reasoning, tool_request,
        clarification_question, term_translations, iteration_count.
    """
    # Paksa finish jika batas iterasi tercapai, tanpa memanggil LLM.
    if state["iteration_count"] >= MAX_ITERATIONS:
        return {
            "action": "finish",
            "current_reasoning": (
                f"Batas maksimum iterasi ({MAX_ITERATIONS}) tercapai. "
                "Menyerahkan seluruh bukti yang sudah terkumpul ke tahap sintesis."
            ),
            "iteration_count": state["iteration_count"] + 1
        }
    
    # Bangun konteks penuh dari state sebelum dikirim ke LLM.
    user_message = _build_supervisor_context(state)

    # LLM memutuskan langkah berikutnya: tool_call, finish, atau clarify.
    supervisor_output = call_structured(
        model_name=SUPERVISOR_MODEL,
        system_prompt=SUPERVISOR_PROMPT,
        user_message=user_message,
        output_schema=SupervisorOutput
    )

    # Simpan reasoning di current_reasoning agar node tool bisa membangun InvestigationStep lengkap.
    return {
        "action": supervisor_output.action,
        "current_reasoning": supervisor_output.reasoning,
        "tool_request": supervisor_output.tool_request,
        "clarification_question": supervisor_output.clarification_question,
        "term_translations": supervisor_output.term_translations,
        "iteration_count": state["iteration_count"] + 1
    }

def _build_supervisor_context(state: AgentState) -> str:
    """Membangun pesan konteks untuk LLM Supervisor dari state saat ini.
    
    Menyertakan pertanyaan aktif, riwayat percakapan room, istilah yang
    sudah diterjemahkan, seluruh jejak investigasi, dan posisi iterasi.


    Args:
        state: State graph saat ini.

    Returns:
        String konteks siap dikirim sebagai user message ke LLM Supervisor.
    """
    sections = []

    # Pertanyaan aktif selalu menjadi section pertama.
    sections.append(f"PERTANYAAN\n{state['user_question']}")

    # Riwayat percakapan hanya disertakan jika ada, untuk pertanyaan lanjutan.
    if state["conversation_history"]:
        history_text = "\n".join(
            f"Pengguna: {turn['content']}"
            if turn['role'] == 'user'
            else f"Jawaban: {turn['content']}"
            for turn in state["conversation_history"]
        )
        sections.append(f"RIWAYAT PERCAKAPAN\n{history_text}")

    # Istilah yang sudah diterjemahkan disertakan agar Supervisor tidak menerjemahkan ulang.
    if state["term_translations"]:
        translations_text = "\n".join(
            f"- {t.term}: {t.definition}"
            for t in state["term_translations"]
        )
        sections.append(f"ISTILAH YANG SUDAH DITERJEMAHKAN\n{translations_text}")

    # Jejak investigasi disertakan agar Supervisor punya konteks penuh dari iterasi sebelumnya.
    if state["investigation_trace"]:
        trace_parts = []
        for step in state["investigation_trace"]:
            trace_parts.append(
                f"Iterasi {step.iteration}\n"
                f"Reasoning: {step.reasoning}\n"
                f"Tool: {step.tool_called}\n"
                f"Input: {step.tool_input}\n"
                f"Output:\n{_format_tool_output(step.tool_output)}"
            )
        sections.append("JEJAK INVESTIGASI\n" + "\n\n".join(trace_parts))

    # Posisi iterasi membantu Supervisor menilai apakah perlu menghemat langkah.
    sections.append(
        f"ITERASI SAAT INI: {state['iteration_count'] + 1} dari {MAX_ITERATIONS}"
    )

    return "\n\n".join(sections)


def _format_tool_output(tool_output) -> str:
    """Memformat output tool menjadi teks ringkas untuk konteks Supervisor.
    
    Args:
        tool_output: SqlToolOutput atau RagToolOutput dari InvestigationStep.

    Returns:
        String representasi output tool, ringkas dan mudah dibaca LLM.
    """
    # Error langsung ditampilkan tanpa memformat isi output.
    if tool_output.error:
        return f"Error: {tool_output.error}"
    
    # SqlToolOutput: tampilkan rows sebagai JSON, atau pesan kosong jika tidak ada hasil.
    if hasattr(tool_output, "rows"):
        if not tool_output.rows:
            return "Query berhasil, tidak ada baris hasil."
        return json.dumps(tool_output.rows, ensure_ascii=False, indent=2)
    
    # RagToolOutput: tampilkan jumlah dokumen relevan dan rangkuman tema.
    if hasattr(tool_output, "summary"):
        return (
            f"({tool_output.doc_count_retrieved} dokumen relevan)\n"
            f"{tool_output.summary}"
        )
    
    return str(tool_output)