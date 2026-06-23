"""
Definisi dan kompilasi StateGraph untuk Olist Insight Assistant.
Merakit seluruh node dan edges menjadi graph yang siap di-invoke.
"""

from langgraph.graph import START, END, StateGraph

from agent.state import AgentState
from agent.supervisor import run_supervisor
from agent.insight_agent import run_insight_agent
from agent.tools.rag_tool import rag_tool_node
from agent.tools.sql_tool import sql_tool_node


def _route_supervisor(state: AgentState) -> str:
    """Menentukan node berikutnya berdasarkan keputusan Supervisor.
    
    Membaca field action dan tool_request dari state untuk menentukan
    ke mana alur graph dilanjutkan setelah Supervisor selesai.

    Args:
        state: State graph saat ini berisi action dari Supervisor.

    Returns:
        Nama node tujuan berikutnya sebagai string.
    """
    # Investigasi selesai, serahkan jejak ke Insight Agent untuk sintesis.
    if state["action"] == "finish":
        return "insight_agent"
    
    # Pertanyaan ambigu atau di luar domain, kembalikan klarifikasi ke pengguna.
    if state["action"] == "clarify":
        return END
    
    # Supervisor meminta tool, routing ke tool yang sesuai berdasarkan tool_request.
    if state["tool_request"] is not None and state["tool_request"].tool_name == "sql_tool":
        return "sql_tool"

    return "rag_tool"


# Inisialisasi builder dengan AgentState sebagai schema state graph.
builder = StateGraph(AgentState)

# Daftarkan seluruh node beserta fungsi eksekusinya.
builder.add_node("supervisor", run_supervisor)
builder.add_node("sql_tool", sql_tool_node)
builder.add_node("rag_tool", rag_tool_node)
builder.add_node("insight_agent", run_insight_agent)

# Entry point graph selalu dimulai dari Supervisor.
builder.add_edge(START, "supervisor")

# Conditional edge dari Supervisor: routing berdasarkan action dan tool_request.
builder.add_conditional_edges("supervisor", _route_supervisor)

# Setelah tool selesai, selalu kembali ke Supervisor untuk iterasi berikutnya.
builder.add_edge("sql_tool", "supervisor")
builder.add_edge("rag_tool", "supervisor")

# Insight Agent selalu menjadi node terakhir sebelum graph selesai.
builder.add_edge("insight_agent", END)

# Compile graph menjadi objek yang siap di-invoke atau di-stream.
graph = builder.compile()