"""
Komponen render jawaban Insight Agent.
Mendeteksi format jawaban dan merender sesuai tipenya.
"""

import streamlit as st


# Marker section untuk deteksi format diagnostik/preskriptif.
_SECTION_FINDINGS = "FINDINGS"
_SECTION_CAUSES = "POSSIBLE CAUSES"
_SECTION_RECOMMENDATIONS = "RECOMMENDATIONS"


def render_answer(final_answer: str) -> None:
    """Merender jawaban Insight Agent sesuai format yang terdeteksi.

    Jika jawaban mengandung ketiga section marker (FINDINGS, POSSIBLE CAUSES,
    RECOMMENDATIONS), dirender sebagai tiga blok terpisah. Jika tidak,
    dirender sebagai teks biasa untuk jawaban faktual atau klarifikasi.

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
        _SECTION_FINDINGS in text
        and _SECTION_CAUSES in text
        and _SECTION_RECOMMENDATIONS in text
    )


def _render_diagnostic(text: str) -> None:
    """Merender jawaban diagnostik sebagai tiga blok section terpisah.

    Memisahkan teks berdasarkan marker section dan merender tiap bagian
    dengan heading yang sesuai.

    Args:
        text: String jawaban diagnostik yang mengandung ketiga section marker.
    """
    sections = _parse_sections(text)

    if sections.get(_SECTION_FINDINGS):
        st.markdown(f"**{_SECTION_FINDINGS}**")
        st.markdown(sections[_SECTION_FINDINGS])

    if sections.get(_SECTION_CAUSES):
        st.markdown(f"**{_SECTION_CAUSES}**")
        st.markdown(sections[_SECTION_CAUSES])

    if sections.get(_SECTION_RECOMMENDATIONS):
        st.markdown(f"**{_SECTION_RECOMMENDATIONS}**")
        st.markdown(sections[_SECTION_RECOMMENDATIONS])


def _parse_sections(text: str) -> dict[str, str]:
    """Memisahkan teks jawaban diagnostik menjadi dict per section.

    Mencari posisi setiap marker dalam teks dan mengekstrak konten
    di antara marker sebagai isi section tersebut.

    Args:
        text: String jawaban diagnostik.

    Returns:
        Dict dengan key nama section dan value isi konten section tersebut.
    """
    markers = [_SECTION_FINDINGS, _SECTION_CAUSES, _SECTION_RECOMMENDATIONS]
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