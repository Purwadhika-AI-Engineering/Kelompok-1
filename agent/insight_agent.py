"""
Node Insight Agent untuk Olist Insight Assistant.
Mensintesis seluruh jejak investigasi menjadi jawaban final dengan
kedalaman adaptif: ringkas untuk pertanyaan faktual, tiga section
untuk pertanyaan diagnostik dan preskriptif.
"""

import json

from agent.prompts.insight_prompt import INSIGHT_PROMPT
from agent.state import AgentState
from config import INSIGHT_AGENT_MAX_TOKENS, INSIGHT_AGENT_MODEL
from services.llm_service import call_text


def run_insight_agent(state: AgentState) -> dict:
    """Mensintesis jejak investigasi menjadi jawaban final.

    Membaca seluruh jejak investigasi dari state, membangun konteks
    lengkap, memanggil LLM untuk sintesis, dan mengembalikan jawaban
    final sebagai teks bebas.

    Args:
        state: State graph berisi pertanyaan awal dan seluruh jejak investigasi.

    Returns:
        Dict update state dengan field final_answer terisi.
    """
    # Bangun konteks penuh dari jejak investigasi sebelum dikirim ke LLM.
    user_message = _build_insight_context(state)

    # LLM mensintesis seluruh jejak menjadi jawaban final adaptif.
    final_answer = call_text(
        model_name=INSIGHT_AGENT_MODEL,
        system_prompt=INSIGHT_PROMPT,
        user_message=user_message,
        max_tokens=INSIGHT_AGENT_MAX_TOKENS,
    )

    return {"final_answer": final_answer}


def _build_insight_context(state: AgentState) -> str:
    """Membangun pesan konteks untuk LLM Insight Agent dari seluruh jejak investigasi.

    Menyertakan pertanyaan awal, istilah yang diterjemahkan, dan seluruh
    langkah Reason-Act-Observe dalam urutan kronologis.

    Args:
        state: State graph saat ini.

    Returns:
        String konteks lengkap siap dikirim sebagai user message ke LLM Insight Agent.
    """
    sections = []

    # Pertanyaan awal selalu disertakan agar sintesis tetap relevan dengan yang ditanya.
    sections.append(f"PERTANYAAN AWAL\n{state['user_question']}")

    # Istilah yang diterjemahkan disertakan agar Insight Agent bisa menyatakannya transparan.
    if state["term_translations"]:
        translations_text = "\n".join(
            f"- {t.term}: {t.definition}"
            for t in state["term_translations"]
        )
        sections.append(f"ISTILAH YANG DITERJEMAHKAN\n{translations_text}")

    # Seluruh jejak investigasi disertakan dalam urutan kronologis untuk sintesis lengkap.
    if state["investigation_trace"]:
        trace_parts = []
        for step in state["investigation_trace"]:
            trace_parts.append(
                f"Langkah {step.iteration}\n"
                f"Reasoning investigator: {step.reasoning}\n"
                f"Tool: {step.tool_called}\n"
                f"Input ke tool: {step.tool_input}\n"
                f"Hasil:\n{_format_tool_output(step.tool_output)}"
            )
        sections.append(
            "JEJAK INVESTIGASI LENGKAP\n" + "\n\n".join(trace_parts)
        )

    return "\n\n".join(sections)


def _format_tool_output(tool_output) -> str:
    """Memformat output tool menjadi teks kaya untuk konteks Insight Agent.

    Berbeda dari versi Supervisor yang ringkas, versi ini menyertakan
    seluruh detail output agar Insight Agent bisa mensintesis dengan lengkap.

    Args:
        tool_output: SqlToolOutput atau RagToolOutput dari InvestigationStep.

    Returns:
        String representasi output tool dengan detail penuh.
    """
    # Error langsung ditampilkan agar Insight Agent tahu langkah ini gagal.
    if tool_output.error:
        return f"ERROR: {tool_output.error}"

    # SqlToolOutput: sertakan query yang dipakai dan seluruh baris hasil.
    if hasattr(tool_output, "rows"):
        if not tool_output.rows:
            return f"Query: {tool_output.query_used}\nHasil: tidak ada baris."
        rows_text = json.dumps(tool_output.rows, ensure_ascii=False, indent=2)
        return f"Query: {tool_output.query_used}\nHasil ({len(tool_output.rows)} baris):\n{rows_text}"

    # RagToolOutput: sertakan filter, jumlah dokumen, dan rangkuman tema.
    if hasattr(tool_output, "summary"):
        filters_text = str(tool_output.filters_applied) if tool_output.filters_applied else "tanpa filter"
        return (
            f"Filter: {filters_text}\n"
            f"Dokumen relevan: {tool_output.doc_count_retrieved}\n"
            f"Rangkuman:\n{tool_output.summary}"
        )

    return str(tool_output)