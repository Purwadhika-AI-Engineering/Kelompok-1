"""
Konstanta non-sensitif untuk seluruh sistem Olist Insigt Assistant.
Credentials dan nilai sensitif diload dari environment variable, bukan dari sini.
"""


# ------------------------------ #
# LLM Models
# ------------------------------ #
SUPERVISOR_MODEL = "gpt-5.4"
INSIGHT_AGENT_MODEL = "gpt-5.4"
SQL_TOOL_MODEL = "gpt-5.4-mini"
RAG_TOOL_MODEL = "gpt-5.4-mini"


# ------------------------------ #
# Embeddiing
# ------------------------------ #
EMBEDDING_MODEL = "text-embedding-3-large"
VECTOR_DIMENSION = 3072


# ------------------------------ #
# Qdrant
# ------------------------------ #
QDRANT_COLLECTION_NAME = "olist_reviews"


# ------------------------------ #
# Database
# ------------------------------ #
DB_PATH = pass
DB_URI = f"file:{DB_PATH}?mode=ro"


# ------------------------------ #
# Retrieval
# ------------------------------ #
TOP_K = 25


# ------------------------------ #
# ReAct Loop
# ------------------------------ #
MAX_ITERATIONS = 7


# ------------------------------ #
# Memory dan Session
# ------------------------------ #
SLIDING_WINDOW = 20
MAX_ROOMS = 5