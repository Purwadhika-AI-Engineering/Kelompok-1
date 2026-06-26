"""
Komponen render jawaban Insight Agent.
Mendeteksi format jawaban dan merender sesuai tipenya.
"""

import streamlit as st


# Marker section sesuai format tiga section di insight_prompt.py.
_SECTION_TEMUAN_DATA = "TEMUAN DATA"
_SECTION_KEMUNGKINAN_PENYEBAB = "KEMUNGKINAN PENYEBAB DAN REASONING"
_SECTION_REKOMENDASI = "REKOMENDASI DAN CATATAN"


def render_answer(final_answer: str) -> None:
    """Merender jawaban Insight Agent sesuai format yang terdeteksi.

    Jika jawaban mengandung ketiga section marker, dirender sebagai tiga
    blok terpisah. Jika tidak, dirender sebagai teks biasa untuk jawaban
    faktual atau clarification question.

    Args:
        final_answer: String jawaban dari Insight Agent atau clarification_question.
    """
    if _is_diagnostic(final_answer):
        _render_diagnostic(final_answer)
    else:
        # Jawaban faktual atau clarification question: render langsung sebagai markdown.
        st.markdown(final_answer)


def _is_diagnostic(text: str) -> bool:
    """Mengecek apakah jawaban berformat diagnostik dengan tiga section.

    Args:
        text: String jawaban dari Insight Agent.

    Returns:
        True jika ketiga section marker ditemukan, False jika tidak.
    """
    return (
        _SECTION_TEMUAN_DATA in text
        and _SECTION_KEMUNGKINAN_PENYEBAB in text
        and _SECTION_REKOMENDASI in text
    )


def _render_diagnostic(text: str) -> None:
    """Merender jawaban diagnostik sebagai tiga blok section terpisah.

    Args:
        text: String jawaban diagnostik yang mengandung ketiga section marker.
    """
    sections = _parse_sections(text)

    if sections.get(_SECTION_TEMUAN_DATA):
        st.markdown(f"**{_SECTION_TEMUAN_DATA}**")
        st.markdown(sections[_SECTION_TEMUAN_DATA])

    if sections.get(_SECTION_KEMUNGKINAN_PENYEBAB):
        st.divider()
        st.markdown(f"**{_SECTION_KEMUNGKINAN_PENYEBAB}**")
        st.markdown(sections[_SECTION_KEMUNGKINAN_PENYEBAB])

    if sections.get(_SECTION_REKOMENDASI):
        st.divider()
        st.markdown(f"**{_SECTION_REKOMENDASI}**")
        st.markdown(sections[_SECTION_REKOMENDASI])


def _parse_sections(text: str) -> dict[str, str]:
    """Memisahkan teks jawaban diagnostik menjadi dict per section.

    Args:
        text: String jawaban diagnostik.

    Returns:
        Dict dengan key nama section dan value isi konten section tersebut.
    """
    markers = [_SECTION_TEMUAN_DATA, _SECTION_KEMUNGKINAN_PENYEBAB, _SECTION_REKOMENDASI]
    positions = {}

    # Cari posisi awal setiap marker di dalam teks.
    for marker in markers:
        idx = text.find(marker)
        if idx != -1:
            positions[marker] = idx

    # Urutkan marker berdasarkan posisi kemunculan di teks.
    ordered = sorted(positions.items(), key=lambda x: x[1])

    sections = {}
    for i, (marker, start) in enumerate(ordered):
        # Konten section dimulai setelah marker hingga awal marker berikutnya.
        content_start = start + len(marker)
        content_end = ordered[i + 1][1] if i + 1 < len(ordered) else len(text)
        sections[marker] = text[content_start:content_end].strip()

    return sections