"""
Entry point Streamlit untuk Olist Insight Assistant.
Mengorkestrasi sidebar, chat history, SSE consumption, dan render jawaban.
"""

import json

import httpx
import streamlit as st

from components.answer import render_answer
from components.sidebar import init_room_state, render_sidebar
from components.view_sources import render_view_sources


# URL endpoint FastAPI yang dikonsumsi Streamlit.
_BACKEND_URL = "http://localhost:8000/investigate"

# Pemetaan nama teknis node ke label tampilan di loading state.
_STEP_LABELS = {
    "sql_tool": "Query transaction data",
    "rag_tool": "Retrieve customer reviews",
    "insight_agent": "Synthesizing insights",
}


def _init_app() -> None:
    """Menginisialisasi konfigurasi halaman dan session state aplikasi.

    Dipanggil sekali di awal setiap rerun sebelum komponen apapun dirender.
    """
    st.set_page_config(
        page_title="Olist Insight Assistant",
        layout="wide",
    )
    init_room_state()


def _render_empty_state() -> None:
    """Merender halaman awal saat belum ada room yang aktif.

    Menampilkan judul, kapabilitas sistem, dan contoh pertanyaan sebagai
    panduan untuk pengguna baru.
    """
    _, col, _ = st.columns([1, 2, 1])

    with col:
        st.title("🤖 Olist Insight Assistant")
        st.caption("Investigasi data e-commerce Olist dengan pertanyaan dalam bahasa natural.")
        st.divider()

        st.markdown("**Apa yang bisa saya bantu?**")
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("🔍 **Investigasi Diagnostik**")
        with col_b:
            st.markdown("📊 **Analisis Kuantitatif**")
        with col_c:
            st.markdown("💬 **Analisis Kualitatif**")

        st.divider()

        st.markdown("**Coba tanyakan:**")

        # Tiga contoh pertanyaan mewakili tipe investigasi berbeda.
        st.markdown("Kategori produk mana yang menghasilkan revenue tertinggi di 2018?")
        st.caption("Analisis Kuantitatif")
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("Kenapa review score furniture turun di Q3 2018?")
        st.caption("Investigasi Diagnostik")
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("Apa keluhan utama pelanggan pada pesanan dengan rating 1-2 bintang?")
        st.caption("Analisis Kualitatif")


def _render_chat_history(room: dict) -> None:
    """Merender seluruh riwayat pesan room yang aktif.

    Args:
        room: Dict data room aktif berisi messages dan conversation_history.
    """
    for msg in room["messages"]:
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                render_answer(msg["content"])
                render_view_sources(
                    msg.get("investigation_trace", []),
                    msg.get("term_translations", []),
                )


def _render_loading(placeholder, completed_steps: list[str]) -> None:
    """Mengupdate loading state dengan daftar langkah yang sudah selesai.

    Args:
        placeholder: st.empty() container yang diupdate setiap ada langkah baru.
        completed_steps: List label langkah yang sudah selesai sampai saat ini.
    """
    with placeholder.container():
        st.markdown("**AI Assistant is investigating...**")
        for step in completed_steps:
            st.markdown(f"✓ {step}")
        st.markdown("Please wait...")


def _stream_and_render(question: str, room: dict) -> None:
    """Mengirim pertanyaan ke FastAPI, mengkonsumsi SSE, dan merender loading state.

    Merender pesan user, loading state dinamis selama stream berlangsung,
    lalu menyimpan hasil ke session state. Tidak merender jawaban assistant
    karena render dilakukan oleh main() via _render_chat_history setelah rerun.

    Args:
        question: Pertanyaan yang dikirim user.
        room: Dict data room aktif untuk mengambil conversation_history.
    """
    # Simpan dan render pesan user sebelum stream dimulai.
    room["messages"].append({"role": "user", "content": question})
    room["conversation_history"].append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    # Buat satu placeholder untuk loading state yang diupdate per progress event.
    loading_placeholder = st.empty()
    completed_steps = []

    payload = {
        "user_question": question,
        "conversation_history": room["conversation_history"],
    }

    final_answer = ""
    investigation_trace = []
    term_translations = []

    try:
        with httpx.Client(timeout=120) as client:
            with client.stream("POST", _BACKEND_URL, json=payload) as response:
                for line in response.iter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = json.loads(line[len("data: "):])
                    event_type = data.get("type")

                    if event_type == "progress":
                        # Tambah satu baris centang ke loading state per progress event.
                        step_name = data.get("step_name", "")
                        label = _STEP_LABELS.get(step_name, step_name)
                        completed_steps.append(label)
                        _render_loading(loading_placeholder, completed_steps)

                    elif event_type == "final":
                        final_answer = data.get("final_answer", "")
                        investigation_trace = data.get("investigation_trace", [])
                        term_translations = data.get("term_translations", [])

    except httpx.RequestError as e:
        loading_placeholder.empty()
        st.error(f"Koneksi ke backend gagal: {e}")
        # Hapus pesan user yang sudah disimpan jika koneksi gagal.
        room["messages"].pop()
        room["conversation_history"].pop()
        return

    loading_placeholder.empty()

    # Simpan jawaban assistant ke session state setelah stream selesai.
    room["messages"].append({
        "role": "assistant",
        "content": final_answer,
        "investigation_trace": investigation_trace,
        "term_translations": term_translations,
    })
    room["conversation_history"].append({"role": "assistant", "content": final_answer})


def main() -> None:
    """Fungsi utama yang mengorkestrasi seluruh alur aplikasi Streamlit.

    Dipanggil setiap rerun. Merender sidebar, menentukan state halaman,
    dan menangani input user.
    """
    _init_app()

    with st.sidebar:
        render_sidebar()

    active_slot = st.session_state.active_room
    if active_slot is None:
        _render_empty_state()
        return

    room = st.session_state.rooms[active_slot]

    # Render seluruh history room aktif -- satu-satunya tempat render history.
    _render_chat_history(room)

    question = st.chat_input(
        "Ask follow-up question..." if room["messages"] else "Ask anything...",
    )

    if question:
        # Jalankan stream -- memblock thread sampai selesai.
        _stream_and_render(question, room)

        # Rerun setelah stream selesai agar UI sinkron dengan session state.
        st.rerun()


if __name__ == "__main__":
    main()