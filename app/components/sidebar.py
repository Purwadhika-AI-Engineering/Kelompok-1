"""
Komponen sidebar untuk manajemen room chat.
Menangani pembuatan, penutupan, pergantian, dan penggantian nama room.
"""

import streamlit as st

from config import MAX_ROOMS


# Label default per slot, urutan A-E sesuai indeks slot 0-4.
_SLOT_LABELS = ["A", "B", "C", "D", "E"]


def init_room_state() -> None:
    """Menginisialisasi seluruh session state yang dibutuhkan manajemen room.

    Dipanggil sekali di awal main.py sebelum komponen apapun dirender.
    Tidak melakukan apapun jika state sudah ada agar tidak menimpa data aktif.
    """
    if "rooms" not in st.session_state:
        # Dict room: key = slot index (0-4), value = dict data room.
        st.session_state.rooms = {}
    if "active_room" not in st.session_state:
        # Slot index room yang sedang aktif, None jika belum ada room.
        st.session_state.active_room = None
    if "editing_room" not in st.session_state:
        # Slot index room yang sedang dalam mode edit nama, None jika tidak ada.
        st.session_state.editing_room = None
    if "room_counter" not in st.session_state:
        # Counter internal untuk memastikan widget key unik antar rerun.
        st.session_state.room_counter = 0


def _get_free_slot() -> int | None:
    """Mencari slot terkecil yang belum terisi room.

    Returns:
        Indeks slot kosong pertama (0-4), atau None jika semua slot terisi.
    """
    for i in range(MAX_ROOMS):
        if i not in st.session_state.rooms:
            return i
    return None


def _create_room() -> None:
    """Membuat room baru di slot kosong terkecil yang tersedia.

    Tidak melakukan apapun jika semua slot sudah terisi.
    Room baru langsung dijadikan room aktif.
    """
    slot = _get_free_slot()
    if slot is None:
        return

    # Increment counter untuk memastikan widget key selalu unik.
    st.session_state.room_counter += 1
    label = _SLOT_LABELS[slot]
    st.session_state.rooms[slot] = {
        "name": f"Room {label}",       # Nama default berdasarkan slot.
        "custom_name": None,           # None berarti belum pernah direname.
        "messages": [],                # Riwayat pesan untuk render chat bubble.
        "conversation_history": [],    # Riwayat format OpenAI untuk dikirim ke FastAPI.
    }
    st.session_state.active_room = slot


def _close_room(slot: int) -> None:
    """Menutup room pada slot tertentu dan membebaskan slotnya.

    Jika room yang ditutup adalah room aktif, pindah ke room lain yang masih ada.

    Args:
        slot: Indeks slot room yang akan ditutup.
    """
    del st.session_state.rooms[slot]

    # Pindah ke room lain jika room yang ditutup adalah room aktif.
    if st.session_state.active_room == slot:
        remaining = list(st.session_state.rooms.keys())
        st.session_state.active_room = remaining[0] if remaining else None


def _render_room_item(slot: int, room: dict) -> None:
    """Merender satu baris room di sidebar beserta tombol edit dan close.

    Args:
        slot: Indeks slot room yang dirender.
        room: Dict data room berisi name, custom_name, messages, conversation_history.
    """
    display_name = room["custom_name"] or room["name"]
    is_active = st.session_state.active_room == slot
    # Bullet aktif (filled) vs tidak aktif (empty) sesuai mockup.
    bullet = "●" if is_active else "○"

    col_name, col_edit, col_close = st.columns([5, 1, 1])

    with col_name:
        if st.session_state.editing_room == slot:
            # Mode edit: tampilkan text input dengan nama saat ini sebagai value awal.
            new_name = st.text_input(
                "Nama room",
                value=display_name,
                key=f"edit_input_{slot}_{st.session_state.room_counter}",
                label_visibility="collapsed",
            )
            # Simpan nama baru jika user mengubah dan menekan Enter.
            if new_name and new_name != display_name:
                st.session_state.rooms[slot]["custom_name"] = new_name
                st.session_state.editing_room = None
                st.rerun()
        else:
            # Mode normal: tampilkan nama room sebagai tombol untuk switch.
            if st.button(
                f"{bullet} {display_name}",
                key=f"room_btn_{slot}_{st.session_state.room_counter}",
                use_container_width=True,
            ):
                st.session_state.active_room = slot
                st.session_state.editing_room = None
                st.rerun()

    with col_edit:
        # Tombol pensil untuk masuk mode edit nama room.
        if st.button("✏️", key=f"edit_btn_{slot}_{st.session_state.room_counter}"):
            st.session_state.editing_room = slot
            st.rerun()

    with col_close:
        # Tombol X untuk menutup room.
        if st.button("✕", key=f"close_btn_{slot}_{st.session_state.room_counter}"):
            _close_room(slot)
            st.rerun()


def render_sidebar() -> None:
    """Merender seluruh konten sidebar: header, tombol new room, dan daftar room.

    Dipanggil dari main.py di dalam blok with st.sidebar.
    """
    st.title("Olist Insight Assistant")

    # Tampilkan warning max room atau tombol new room.
    if len(st.session_state.rooms) >= MAX_ROOMS:
        st.warning(
            "Maximum rooms reached. Please close one room before creating a new one."
        )
    else:
        if st.button("+ New Room", use_container_width=True):
            _create_room()
            st.rerun()

    st.divider()

    # Render setiap room yang ada, diurutkan berdasarkan indeks slot.
    for slot in sorted(st.session_state.rooms.keys()):
        _render_room_item(slot, st.session_state.rooms[slot])