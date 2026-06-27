# Olist Insight Assistant

An agentic web analytics application that allows Business Analysts to investigate Brazilian e-commerce data using natural language questions and receive structured analytical answers with reasoning and recommendations.

Built on the [Olist E-Commerce Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) covering September 2016 to October 2018.

---

## What It Does

Instead of running a single query and returning raw results, the system investigates iteratively. A Supervisor Agent reasons about what evidence is needed, calls the appropriate tool, reads the result, and decides whether to continue or synthesize — repeating until the investigation is complete. A separate Insight Agent then synthesizes all findings into a structured analytical answer.

Three types of questions are supported:

- **Quantitative Analysis** — "What is the average delivery duration and late delivery rate per state in 2018?"
- **Diagnostic Investigation** — "Which product categories disappoint customers the most, and what are they actually complaining about?"
- **Qualitative Analysis** — "What are the main complaints from customers with 1-2 star ratings?"

---

## Architecture

```
User (Browser)
    │
    ▼
Streamlit Frontend
    │  SSE stream
    ▼
FastAPI Backend (/investigate)
    │
    ▼
LangGraph Graph
    │
    ├── Supervisor Agent (ReAct loop)
    │       │
    │       ├── sql_tool ──► SQLite (order_summary, item_detail)
    │       │
    │       └── rag_tool ──► Qdrant Cloud (olist_reviews, 3072-dim)
    │
    └── Insight Agent (synthesis)
            │
            ▼
    Structured answer streamed back to UI
```

**Two-stage linear flow:**

1. **Supervisor Agent** runs a ReAct loop — reasons about what evidence is needed, calls `sql_tool` for quantitative evidence or `rag_tool` for qualitative evidence (or both in sequence), and repeats until investigation is complete or the maximum iteration limit is reached.
2. **Insight Agent** receives the full investigation trace and synthesizes a structured answer — concise for factual questions, three-section format (Data Findings, Possible Causes, Recommendations) for diagnostic and prescriptive questions.

**Tool selection is based on the type of evidence needed, not the topic:**
- `sql_tool` — for HOW MANY, HOW LARGE, or WHETHER A PATTERN EXISTS
- `rag_tool` — for WHAT CUSTOMERS SAY or WHY from their perspective

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent Orchestration | LangGraph |
| Backend API | FastAPI (SSE streaming) |
| Frontend | Streamlit |
| LLM — Supervisor & Insight Agent | GPT-5.4 |
| LLM — sql_tool & rag_tool | GPT-5.4 Mini |
| Embedding | text-embedding-3-large (3072 dimensions) |
| Vector Database | Qdrant Cloud |
| Structured Database | SQLite |
| Observability | Langfuse |
| Deployment | Docker, GCP Cloud Run |

---

## Project Structure

```
olist-insight-assistant/
├── agent/
│   ├── graph.py              # LangGraph graph: nodes, edges, and routing logic
│   ├── supervisor.py         # Supervisor Agent node: ReAct loop and iterative decision-making
│   ├── insight_agent.py      # Insight Agent node: synthesizes investigation trace into final answer
│   ├── state.py              # AgentState and supporting Pydantic classes
│   ├── tools/
│   │   ├── sql_tool.py       # Text-to-SQL tool and its node wrapper
│   │   └── rag_tool.py       # Semantic review search tool and its node wrapper
│   └── prompts/
│       ├── supervisor_prompt.py  # Supervisor Agent system prompt
│       ├── sql_prompt.py         # sql_tool system prompt
│       ├── rag_prompt.py         # rag_tool filter extraction and summarization system prompts
│       └── insight_prompt.py     # Insight Agent system prompt
├── api/
│   ├── main.py               # FastAPI entry point, /investigate SSE endpoint, structured JSON logging
│   └── schemas.py            # Pydantic schemas for SSE events
├── app/
│   ├── main.py               # Streamlit entry point, session state and multi-room management
│   └── components/
│       ├── answer.py         # Rendering of Insight Agent final answer
│       ├── sidebar.py        # Sidebar component for room management
│       └── view_sources.py   # Investigation trace display (sources and Supervisor steps)
├── services/
│   ├── llm_service.py        # LangChain OpenAI wrapper for Supervisor, Insight Agent, and tools
│   ├── embedding_service.py  # OpenAI embedding for rag_tool queries
│   ├── sqlite_service.py     # Read-only SQLite connection for sql_tool
│   └── qdrant_service.py     # Semantic search and metadata filtering to Qdrant Cloud
├── observability/
│   ├── langfuse_setup.py     # Langfuse callback handler for ReAct loop tracing
│   └── logging_setup.py      # Structured JSON logging configuration to stdout
├── scripts/
│   ├── create_db.py          # SQLite ingestion pipeline from original Olist CSV files
│   └── create_rag.py         # Qdrant ingestion pipeline: embedding and uploading reviews
├── data/
│   └── olist.db              # SQLite database (not committed to repo)
├── config.py                 # Non-sensitive constants and application configuration
├── pyproject.toml            # Editable install configuration for cross-platform import resolution
├── requirements.txt          # Python dependencies
├── Dockerfile                # Docker image build configuration
└── start.sh                  # Container entrypoint: runs FastAPI and Streamlit simultaneously
```

---

## Prerequisites

Before running this project, make sure the following are available:

- Python 3.12
- Docker Desktop
- An OpenAI API key with access to GPT-5.4 and text-embedding-3-large
- A Qdrant Cloud cluster with the `olist_reviews` collection ingested
- A Langfuse account (US region) with a project created

---

## Local Development

**1. Clone the repository:**
```bash
git clone https://github.com/Purwadhika-AI-Engineering/Kelompok-1.git
cd Kelompok-1
```

**2. Create and activate a virtual environment:**
```bash
python -m venv .venv
```

macOS/Linux:
```bash
source .venv/bin/activate
```

Windows:
```bash
.venv\Scripts\activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
pip install -e .
```

**4. Set up environment variables:**
```bash
cp .env.example .env
```

Fill in `.env` with your actual credentials:
```
OPENAI_API_KEY=your_openai_api_key
QDRANT_URL=your_qdrant_cluster_url
QDRANT_API_KEY=your_qdrant_api_key
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=https://us.cloud.langfuse.com
```

**5. Run the data pipeline** (only needed once, requires the original Olist CSV files):
```bash
python scripts/create_db.py
python scripts/create_rag.py
```

**6. Start the backend:**
```bash
uvicorn api.main:app --reload
```

**7. Start the frontend** (in a separate terminal):
```bash
streamlit run app/main.py
```

Open `http://localhost:8501` in your browser.

---

## Docker

**Build the image:**
```bash
docker build -t olist-insight-assistant .
```

**Run the container:**
```bash
docker run --env-file .env -p 8080:8080 olist-insight-assistant
```

Open `http://localhost:8080` in your browser.

The container runs both FastAPI (port 8000, internal) and Streamlit (port 8080, public-facing) in a single container via `start.sh`.

---

## Deployment

The application is deployed to **GCP Cloud Run** using a single Docker container that runs FastAPI (internal, port 8000) and Streamlit (public-facing, port 8080) simultaneously via `start.sh`. The image is pushed to Artifact Registry in the `asia-southeast1` region before being deployed to Cloud Run.

---

## Data Architecture

Two SQLite derived tables built from the original nine Olist CSV files:

- **`order_summary`** — one row per order. Contains order status, timestamps, customer location, review score, payment info, and delivery metrics.
- **`item_detail`** — one row per item per order. Contains product category, seller, price, freight, and product dimensions.

One Qdrant collection:

- **`olist_reviews`** — customer review texts embedded with text-embedding-3-large (3072 dimensions). Six metadata fields available for filtering: `review_score`, `customer_state`, `customer_city`, `product_category`, `review_year`, `review_month`.

---

## Team

| Name | Role |
|---|---|
| Muhammad Daffa Al Hanif | AI Orchestration — Supervisor Agent, Insight Agent, sql_tool, rag_tool, LangGraph, FastAPI, Langfuse |
| Muhammad Fachreza Alghifari | Data Engineer — SQLite pipeline, Qdrant ingestion, data cleaning, feature engineering |
| Medina Assyifa | UI Development, QA & Monitoring — Streamlit, end-to-end testing, Langfuse dashboard monitoring |
