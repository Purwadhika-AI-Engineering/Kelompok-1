"""
Komponen render View Sources dari investigation_trace dan term_translations.
Ditampilkan sebagai expander di bawah jawaban Insight Agent.
"""

import streamlit as st


def render_view_sources(
    investigation_trace: list[dict],
    term_translations: list[dict],
) -> None:
    """Merender dropdown View Sources berisi sumber data investigasi.

    Iterasi setiap langkah di investigation_trace dan render blok sesuai
    tool yang dipanggil. Setelah semua trace, render Definitions jika ada.
    Tidak merender apapun jika investigation_trace kosong (pertanyaan ambigu).

    Args:
        investigation_trace: List TraceStep dari FinalEvent.
        term_translations: List TermTranslationResponse dari FinalEvent.
    """
    if not investigation_trace:
        return

    with st.expander("▼ View Sources"):
        for step in investigation_trace:
            tool_called = step.get("tool_called", "")

            if tool_called == "sql_tool":
                _render_sql_section(step)
            elif tool_called == "rag_tool":
                _render_rag_section(step)

            st.divider()

        if term_translations:
            _render_definitions_section(term_translations)


def _render_sql_section(step: dict) -> None:
    """Merender blok SQL Query dari satu langkah sql_tool.

    Args:
        step: Satu elemen investigation_trace dengan tool_called == sql_tool.
    """
    st.markdown("**SQL Query**")
    # Render query sebagai code block agar formatting SQL terbaca jelas.
    st.code(step.get("query_used", ""), language="sql")


def _render_rag_section(step: dict) -> None:
    """Merender blok Review Retrieval dari satu langkah rag_tool.

    Args:
        step: Satu elemen investigation_trace dengan tool_called == rag_tool.
    """
    st.markdown("**Review Retrieval**")

    filters = step.get("filters_applied", {})
    doc_count = step.get("doc_count_retrieved", 0)

    # Render setiap filter metadata sebagai pasangan label dan nilai.
    for key, value in filters.items():
        st.markdown(f"**{_format_filter_label(key)}**")
        st.markdown(_format_filter_value(value))

    st.markdown("**Retrieved**")
    st.markdown(f"{doc_count} reviews")


def _render_definitions_section(term_translations: list[dict]) -> None:
    """Merender blok Definitions berisi istilah relatif dan definisinya.

    Args:
        term_translations: List TermTranslationResponse dari FinalEvent.
    """
    st.markdown("**Definitions**")
    for translation in term_translations:
        st.markdown(f"**{translation.get('term', '')}**")
        st.markdown(translation.get("definition", ""))


def _format_filter_label(key: str) -> str:
    """Mengubah key metadata Qdrant menjadi label yang terbaca manusia.

    Args:
        key: Nama field metadata, contoh: review_score, customer_state.

    Returns:
        Label yang diformat dengan title case dan tanpa underscore.
    """
    return key.replace("_", " ").title()


def _format_filter_value(value) -> str:
    """Mengubah nilai filter metadata menjadi string yang terbaca manusia.

    Nilai kategorikal dikembalikan langsung. Nilai range (dict dengan gte/lte)
    diformat menjadi string rentang yang natural.

    Args:
        value: Nilai filter, bisa string atau dict range gte/lte.

    Returns:
        String representasi nilai filter.
    """
    if isinstance(value, dict):
        # Format range object gte/lte menjadi string rentang yang natural.
        gte = value.get("gte")
        lte = value.get("lte")
        if gte is not None and lte is not None:
            return f"{gte} - {lte}"
        if gte is not None:
            return f">= {gte}"
        if lte is not None:
            return f"<= {lte}"
    return str(value)