"""
FastAPI entry point untuk Olist Insight Assistant.
Mengekspos endpoint /investigate sebagai SSE streaming yang memanggil
graph LangGraph dan meneruskan update ke client secara real-time.
"""

import json
from typing import Literal, cast

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from agent.graph import graph
from agent.state import AgentState, build_initial_state
from api.schemas import (
    FinalEvent,
    InvestigateRequest,
    ProgressEvent,
    TermTranslationResponse,
    TraceStep,
)
from config import SLIDING_WINDOW

app = FastAPI()

@app.get("/health")
async def health_check():
    """Mengecek status server untuk keperluan health check deployment.

    Returns:
        Dict status server.
    """
    return {"status": "healthy"}


# Node tool yang menghasilkan progress event saat selesai.
_TOOL_NODES = {"sql_tool", "rag_tool"}


@app.post("/investigate")
async def investigate(request: InvestigateRequest) -> StreamingResponse:
    """Endpoint utama investigasi, mengembalikan response sebagai SSE stream.

    Menerima pertanyaan dan riwayat percakapan, menginvoke graph LangGraph,
    dan meneruskan update ke client sebagai Server-Sent Events. Setiap node
    tool yang selesai menghasilkan progress event, lalu satu final event
    dikirim di akhir stream berisi jawaban dan seluruh jejak investigasi.

    Args:
        request: Pertanyaan pengguna dan riwayat percakapan room aktif.

    Returns:
        StreamingResponse dengan media type text/event-stream.
    """
    windowed_history = request.conversation_history[-SLIDING_WINDOW:]

    initial_state = build_initial_state(
        user_question=request.user_question,
        conversation_history=windowed_history,
    )

    return StreamingResponse(
        _stream_investigation(initial_state),
        media_type="text/event-stream",
    )


async def _stream_investigation(initial_state: AgentState):
    """Generator SSE yang mengalirkan progress dan final event dari graph.

    Memanggil graph.stream() dan memproses setiap update node. Node tool
    menghasilkan progress event. Trace dan term_translations diakumulasi
    sendiri selama loop berlangsung untuk menghindari kehilangan data akibat
    delta-only nature dari stream_mode updates. Di akhir stream, final event
    dikirim berisi jawaban final dan seluruh jejak investigasi terakumulasi.

    Args:
        initial_state: State awal hasil build_initial_state.

    Yields:
        String SSE berformat 'data: {json}\\n\\n' untuk setiap event.
    """
    accumulated_trace = []
    accumulated_translations = []
    last_node_state = {}

    for state_update in graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_state in state_update.items():
            # Akumulasi trace dari setiap node yang menulisnya.
            if "investigation_trace" in node_state:
                accumulated_trace.extend(node_state["investigation_trace"])

            # Akumulasi term_translations dari setiap node yang menulisnya.
            if "term_translations" in node_state:
                accumulated_translations.extend(node_state["term_translations"])

            # Simpan state node terakhir untuk mengambil final_answer dan clarification_question.
            last_node_state.update(node_state)

            if node_name not in _TOOL_NODES:
                continue

            trace = node_state.get("investigation_trace", [])
            iteration = trace[-1].iteration if trace else 0

            step_name = cast(Literal["sql_tool", "rag_tool", "insight_agent"], node_name)
            event = ProgressEvent(
                step_name=step_name,
                status="done",
                iteration=iteration,
            )
            yield _format_sse(event.model_dump())

    # Kirim progress event untuk Insight Agent sebelum final event.
    yield _format_sse(ProgressEvent(
        step_name="insight_agent",
        status="done",
        iteration=0,
    ).model_dump())

    yield _format_sse(_build_final_event(
        accumulated_trace,
        accumulated_translations,
        last_node_state,
    ))


def _build_final_event(
    accumulated_trace: list,
    accumulated_translations: list,
    last_node_state: dict,
) -> dict:
    """Membangun payload final event dari akumulasi data sepanjang stream.

    Mengambil jawaban final atau pertanyaan klarifikasi dari state node
    terakhir, lalu menyerialisasi seluruh jejak investigasi dan istilah
    yang diterjemahkan untuk View Sources di Streamlit.

    Args:
        accumulated_trace: Seluruh InvestigationStep yang terakumulasi dari semua node.
        accumulated_translations: Seluruh TermTranslation yang terakumulasi dari semua node.
        last_node_state: State node terakhir yang jalan, sumber final_answer
            dan clarification_question.

    Returns:
        Dict payload final event siap diserialisasi ke JSON.
    """
    final_answer = (
        last_node_state.get("final_answer")
        or last_node_state.get("clarification_question")
        or ""
    )

    trace_steps = []
    for step in accumulated_trace:
        tool_output = step.tool_output
        trace_steps.append(TraceStep(
            iteration=step.iteration,
            tool_called=step.tool_called,
            tool_input=step.tool_input,
            query_used=getattr(tool_output, "query_used", ""),
            filters_applied=getattr(tool_output, "filters_applied", {}),
            doc_count_retrieved=getattr(tool_output, "doc_count_retrieved", 0),
        ))

    translations = [
        TermTranslationResponse(term=t.term, definition=t.definition)
        for t in accumulated_translations
    ]

    return FinalEvent(
        final_answer=final_answer,
        investigation_trace=trace_steps,
        term_translations=translations,
    ).model_dump()


def _format_sse(data: dict) -> str:
    """Memformat dict menjadi string SSE sesuai protokol text/event-stream.

    Args:
        data: Dict payload yang akan dikirim sebagai event.

    Returns:
        String SSE berformat 'data: {json}\\n\\n'.
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"