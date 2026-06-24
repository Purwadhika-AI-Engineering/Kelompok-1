import streamlit as st
from datetime import datetime
import json
import requests
from typing import Generator, Optional
import time

# ======================
# PAGE CONFIG
# ======================

st.set_page_config(
    page_title="Olist Insight Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================
# CONFIGURATION
# ======================

FASTAPI_BASE_URL = "http://localhost:8000"  # Update sesuai deployment
SSE_TIMEOUT = 300  # 5 minutes timeout for long investigations

# ======================
# SESSION STATE INITIALIZATION
# ======================

if "rooms" not in st.session_state:
    st.session_state.rooms = {
        "room_1": {
            "name": "Room Chat 1",
            "created_at": datetime.now(),
            "messages": []
        }
    }

if "active_room_id" not in st.session_state:
    st.session_state.active_room_id = "room_1"


# ======================
# SSE STREAMING & BACKEND HELPERS
# ======================

def parse_sse_stream(response_text: str) -> Generator[dict, None, None]:
    """Parse Server-Sent Events stream format.
    
    Args:
        response_text: Raw SSE stream text
        
    Yields:
        Parsed JSON dict from each event
    """
    for line in response_text.split('\n'):
        if line.startswith('data: '):
            try:
                event_data = json.loads(line[6:])  # Remove 'data: ' prefix
                yield event_data
            except json.JSONDecodeError:
                continue


def stream_investigation_sse(user_question: str, conversation_history: list) -> Generator[dict, None, None]:
    """Call /investigate endpoint dan stream events real-time.
    
    Args:
        user_question: User's question
        conversation_history: Previous messages in room
        
    Yields:
        Each event (ProgressEvent or FinalEvent) dari backend
    """
    request_payload = {
        "user_question": user_question,
        "conversation_history": conversation_history
    }
    
    try:
        response = requests.post(
            f"{FASTAPI_BASE_URL}/investigate",
            json=request_payload,
            stream=True,
            timeout=SSE_TIMEOUT
        )
        response.raise_for_status()
        
        # Stream events real-time
        for event in parse_sse_stream(response.text):
            yield event
            
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend. Make sure FastAPI server is running at " + FASTAPI_BASE_URL)
        yield {
            "type": "error",
            "message": "Backend connection failed"
        }
    except requests.exceptions.Timeout:
        st.error("⏱️ Investigation timed out. Please try again.")
        yield {
            "type": "error",
            "message": "Request timeout"
        }
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        yield {
            "type": "error",
            "message": str(e)
        }


# ======================
# HELPER FUNCTIONS
# ======================

def create_new_room():
    """Create a new room and switch to it"""
    max_rooms = 5
    
    if len(st.session_state.rooms) >= max_rooms:
        st.error(f"❌ Maximum {max_rooms} rooms reached. Please close one room before creating a new one.")
        return
    
    # Find next available room number (1, 2, 3, 4, 5...)
    # by checking which numbers are already used in room names
    existing_numbers = set()
    for room_data in st.session_state.rooms.values():
        # Extract number from "Room Chat X"
        room_name = room_data["name"]
        try:
            number = int(room_name.split()[-1])
            existing_numbers.add(number)
        except (ValueError, IndexError):
            pass
    
    # Find first available number
    next_number = 1
    while next_number in existing_numbers:
        next_number += 1
    
    # Use unique room_id (can reuse deleted numbers for IDs)
    new_room_id = f"room_{next_number}"
    
    st.session_state.rooms[new_room_id] = {
        "name": f"Room Chat {next_number}",
        "created_at": datetime.now(),
        "messages": []
    }
    
    st.session_state.active_room_id = new_room_id
    st.rerun()


def delete_room(room_id):
    """Delete a room"""
    if room_id in st.session_state.rooms:
        del st.session_state.rooms[room_id]
        
        # Switch to another room if deleted room was active
        if st.session_state.active_room_id == room_id:
            remaining_rooms = list(st.session_state.rooms.keys())
            st.session_state.active_room_id = remaining_rooms[0] if remaining_rooms else None
        
        st.rerun()


def switch_room(room_id):
    """Switch to a different room"""
    st.session_state.active_room_id = room_id
    st.rerun()


def add_message(
    role: str,
    content: str,
    investigation_trace: list = None,
    term_translations: list = None
):
    """Add message to current room's chat history.
    
    Args:
        role: "user" or "assistant"
        content: Message content
        investigation_trace: List of TraceStep from backend
        term_translations: List of TermTranslation from backend
    """
    active_room = st.session_state.rooms[st.session_state.active_room_id]
    
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "investigation_trace": investigation_trace or [],
        "term_translations": term_translations or []
    }
    
    active_room["messages"].append(message)


def get_active_room_messages():
    """Get messages from active room"""
    if st.session_state.active_room_id:
        return st.session_state.rooms[st.session_state.active_room_id]["messages"]
    return []


def get_room_message_count():
    """Get jumlah messages di active room"""
    if st.session_state.active_room_id:
        return len(st.session_state.rooms[st.session_state.active_room_id]["messages"])
    return 0


def clear_room_history():
    """Clear all messages dalam active room"""
    if st.session_state.active_room_id:
        st.session_state.rooms[st.session_state.active_room_id]["messages"] = []
        st.rerun()


def show_clarification_question(clarification: str):
    """Display clarification question (PAGE 5).
    
    Ketika agent butuh clarification, show options untuk user.
    """
    st.warning("🤔 Your question is too broad.")
    st.write("**Which area would you like to investigate?**")
    
    # Parse clarification options dari string atau preset options
    # Placeholder: bisa di-refine sesuai format dari backend
    options = [
        "Delivery",
        "Revenue",
        "Customer Reviews",
        "All areas"
    ]
    
    for option in options:
        if st.button(option, key=f"clarify_{option}", use_container_width=True):
            st.session_state.last_clarification = option
            st.rerun()


def render_answer(message: dict, show_copy_button: bool = True):
    """Render answer based on backend response with transparency."""
    content = message["content"]
    investigation_trace = message.get("investigation_trace", [])
    term_translations = message.get("term_translations", [])
    answer_type = message.get("answer_type")
    
    # Display main answer
    st.write(content)
    
    # Copy button untuk answer
    if show_copy_button:
        col1, col2, col3 = st.columns([0.15, 0.15, 0.7])
        with col1:
            if st.button("📋 Copy", key=f"copy_{message.get('timestamp', '')}"):
                st.toast("Copied to clipboard!", icon="✅")
    
    # Show investigation trace (View Sources)
    if investigation_trace:
        with st.expander("🔍 View Sources", expanded=False):
            st.subheader("Investigation Trace")
            
            for i, step in enumerate(investigation_trace, 1):
                with st.container(border=True):
                    col1, col2, col3 = st.columns([0.15, 0.2, 0.65])
                    
                    with col1:
                        st.caption(f"**Step {i}**")
                        st.caption(f"Iteration: {step['iteration']}")
                    
                    with col2:
                        st.caption(f"**Tool:** {step['tool_called']}")
                    
                    with col3:
                        st.caption(f"Input: `{step['tool_input']}`")
                        
                        if step.get("query_used"):
                            # SQL Query dengan copy button
                            st.caption("**SQL Query:**")
                            col_query, col_copy = st.columns([0.9, 0.1])
                            with col_query:
                                st.code(step['query_used'], language="sql")
                            with col_copy:
                                if st.button("📋", key=f"copy_sql_{i}", help="Copy SQL"):
                                    st.toast("SQL copied!", icon="✅")
                        
                        if step.get("filters_applied"):
                            st.caption(f"**Filters:** {step['filters_applied']}")
                        
                        if step.get("doc_count_retrieved", 0) > 0:
                            st.caption(f"**Documents Retrieved:** {step['doc_count_retrieved']}")
    
    # Show term translations (Definitions)
    if term_translations:
        with st.expander("📚 Definitions", expanded=False):
            st.subheader("Term Translations")
            
            for trans in term_translations:
                with st.container(border=True):
                    st.caption(f"**{trans['term']}**")
                    st.write(trans['definition'])


# ======================
# SIDEBAR
# ======================

with st.sidebar:
    st.title("🤖 Olist Insight Assistant")
    
    # New Room Button
    if st.button("➕ New Room", key="new_room_btn", use_container_width=True):
        create_new_room()
    
    st.divider()
    
    # Room List - SORTED by room number for consistent display
    st.subheader("Rooms", divider=True)
    
    # Sort rooms by their number (1, 2, 3, 4, 5...)
    sorted_rooms = sorted(
        st.session_state.rooms.items(),
        key=lambda x: int(x[1]["name"].split()[-1])  # Extract number from "Room Chat X"
    )
    
    for room_id, room_data in sorted_rooms:
        is_active = room_id == st.session_state.active_room_id
        msg_count = len(room_data["messages"])
        indicator = "●" if is_active else "○"
        
        # Room button + action buttons in one row
        room_col, clear_col, delete_col = st.columns([0.6, 0.2, 0.2], gap="small")
        
        with room_col:
            button_label = f"{indicator} {room_data['name']} ({msg_count})"
            if st.button(
                button_label,
                key=f"room_btn_{room_id}",
                use_container_width=True
            ):
                switch_room(room_id)
        
        with clear_col:
            # Clear button only for active room with messages
            if is_active and msg_count > 0:
                if st.button(
                    "🗑️",
                    key=f"clear_btn_{room_id}",
                    help="Clear chat history",
                    use_container_width=True
                ):
                    clear_room_history()
        
        with delete_col:
            # Delete button always visible
            if st.button(
                "✕",
                key=f"delete_btn_{room_id}",
                help="Delete room",
                use_container_width=True
            ):
                delete_room(room_id)


# ======================
# MAIN CONTENT AREA
# ======================

if not st.session_state.active_room_id:
    st.warning("⚠️ No active room. Please create one.")
else:
    active_room_data = st.session_state.rooms[st.session_state.active_room_id]
    messages = get_active_room_messages()
    
    # Empty State
    if not messages:
        st.title("Olist Insight Assistant")
        
        st.write(
            "Ask questions about Olist data in natural language. "
            "Our AI assistant will investigate the data and provide insights."
        )
        
        st.subheader("Example Questions")
        st.write("• Why did furniture review scores drop in Q3 2018?")
        st.write("• Which category generated the highest revenue?")
        st.write("• What complaints are common among 1-star reviews?")
        
        st.divider()
    
    # Chat History Display
    if messages:
        st.subheader(active_room_data["name"])
        
        for message in messages:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    # Render assistant answer dengan transparency
                    render_answer(message)
                else:
                    # Simple user message
                    st.write(message["content"])
    
    # Chat Input (with unique key to avoid duplicate element error)
    st.divider()
    
    question = st.chat_input(
        "Ask anything...",
        key=f"chat_input_{st.session_state.active_room_id}"
    )
    
    if question:
        # Add user message to history
        add_message("user", question)
        
        # Display user message
        with st.chat_message("user"):
            st.write(question)
        
        # Display assistant response with streaming
        with st.chat_message("assistant"):
            # Placeholder for progress updates
            progress_placeholder = st.empty()
            response_placeholder = st.empty()
            
            # State variables untuk track progress
            progress_steps = []
            final_response = None
            investigation_trace = []
            term_translations = []
            
            # Call backend and stream events
            for event in stream_investigation_sse(
                user_question=question,
                conversation_history=get_active_room_messages()
            ):
                event_type = event.get("type")
                
                if event_type == "progress":
                    # Update progress display
                    step_name = event.get("step_name")
                    iteration = event.get("iteration", 0)
                    
                    # Map step names ke readable labels
                    step_labels = {
                        "sql_tool": "📊 Querying transaction data",
                        "rag_tool": "📚 Retrieving customer reviews",
                        "insight_agent": "✨ Synthesizing insights"
                    }
                    
                    step_label = step_labels.get(step_name, step_name)
                    progress_steps.append(f"✓ {step_label}")
                    
                    with progress_placeholder.container():
                        st.write("**🤖 AI Assistant is investigating...**")
                        for step in progress_steps:
                            st.write(step)
                        if iteration > 0:
                            st.caption(f"Iteration {iteration}")
                
                elif event_type == "final":
                    # Parse final response (bisa final_answer atau clarification_question)
                    final_answer = event.get("final_answer", "")
                    clarification_question = event.get("clarification_question", "")
                    investigation_trace = event.get("investigation_trace", [])
                    term_translations = event.get("term_translations", [])
                    
                    # Clear progress display
                    progress_placeholder.empty()
                    
                    # Handle clarification question case (PAGE 5)
                    if clarification_question and not final_answer:
                        st.warning("🤔 Your question is too broad.")
                        st.write("**Which area would you like to investigate?**")
                        
                        # Predefined clarification options
                        options = ["Delivery", "Revenue", "Customer Reviews"]
                        col1, col2, col3 = st.columns(3)
                        
                        for i, option in enumerate(options):
                            with [col1, col2, col3][i]:
                                if st.button(option, key=f"clarify_{option}_{st.session_state.active_room_id}", use_container_width=True):
                                    # Re-ask with clarification
                                    refined_question = f"{question} (focus on {option})"
                                    st.session_state.clarification_refined = refined_question
                        
                        # Store clarification message
                        add_message(
                            "assistant",
                            clarification_question,
                            investigation_trace=[],
                            term_translations=[]
                        )
                    
                    # Handle normal answer case
                    else:
                        # Store message in history dengan transparency data
                        add_message(
                            "assistant",
                            final_answer,
                            investigation_trace=investigation_trace,
                            term_translations=term_translations
                        )
                        
                        # Render the answer dengan transparency
                        render_answer({
                            "content": final_answer,
                            "investigation_trace": investigation_trace,
                            "term_translations": term_translations
                        })
                
                elif event_type == "error":
                    # Handle error from backend
                    error_msg = event.get("message", "Unknown error")
                    st.error(f"❌ Investigation failed: {error_msg}")
            
            # Re-render to update chat history display
            st.rerun()


# ======================
# FOOTER
# ======================

st.divider()
st.caption(
    f"Active Room: **{st.session_state.rooms[st.session_state.active_room_id]['name']}** | "
    f"Total Rooms: **{len(st.session_state.rooms)}/5**"
)