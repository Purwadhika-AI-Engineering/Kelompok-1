import os
import sqlite3
import dotenv
import pandas as pd
from tqdm import tqdm
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models
from config import *

# Load environmental variables
dotenv.load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not all([OPENAI_KEY, QDRANT_URL, QDRANT_API_KEY]):
    print("❌ Error: Missing required credentials in environment variables.")
    print("💡 Ensure OPENAI_API_KEY, QDRANT_URL, and QDRANT_API_KEY are configured.")
    exit(1)

openai_client = OpenAI(api_key=OPENAI_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Dynamically handle directory references
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
root_dir = os.path.abspath(os.path.join(script_dir, '..'))
db_path = os.path.join(root_dir, 'data', 'olist.db')

if not os.path.exists(db_path):
    print(f"❌ Error: Could not locate SQLite database at {db_path}")
    exit(1)

print(f"📥 Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)

# Extract structured frames from SQLite
order_summary_df = pd.read_sql_query(
    "SELECT order_id, customer_state, customer_city, review_score FROM order_summary", 
    conn
)
item_detail_df = pd.read_sql_query(
    "SELECT order_id, product_category_name_english FROM item_detail", 
    conn
)
conn.close()

# Deduplicate item_detail to get a single categorical product mapped per order context
product_mapping = (
item_detail_df
.groupby('order_id')['product_category_name_english']
.first()
.reset_index()
)
product_mapping.columns = ['order_id', 'product_category']

# Load the base reviews file
print("🧩 Stitching database fields together into metadata frames...")
df = pd.read_csv(os.path.join(root_dir, 'database', 'olist_order_reviews_dataset.csv'))

# Keep only valid text commentary matches
df = df[df['review_comment_message'].notna() & (df['review_comment_message'].str.strip() != '')].copy()
df['review_comment_title'] = df['review_comment_title'].fillna('')

# Preserve review_creation_date from CSV, drop review_score to use the SQL version safely
df = df.drop(columns=['review_score'], errors='ignore')

# Primary join executions
df = df.merge(order_summary_df, on='order_id', how='inner')
df = df.merge(product_mapping, on='order_id', how='left')
df = df[df['review_score'].notna()].copy()

# Extract custom date features: year and month metrics
df['review_answer_timestamp'] = pd.to_datetime(df['review_answer_timestamp'])
df = df[df['review_answer_timestamp'].notna()].copy()
df['review_year'] = df['review_answer_timestamp'].dt.year
df['review_month'] = df['review_answer_timestamp'].dt.month
df['product_category'] = df['product_category'].fillna('unknown')

records = df.to_dict(orient='records')
collection_name = QDRANT_COLLECTION_NAME

print(f"⚙️ Setting up collection '{collection_name}' in Qdrant Cloud...")

# Recreate the collection to clear out old corrupted index sizes cleanly
if collection_name in [c.name for c in qdrant_client.get_collections().collections]:
    print(f"🗑️ Re-creating clean vector collection '{collection_name}'...")
    qdrant_client.delete_collection(collection_name=collection_name)

qdrant_client.create_collection(
    collection_name=collection_name,
    vectors_config=models.VectorParams(size=VECTOR_DIMENSION, distance=models.Distance.COSINE)
)

from qdrant_client.models import PayloadSchemaType
# Buat payload index untuk semua field yang dipakai sebagai filter.
fields_to_index = {
    "review_score": PayloadSchemaType.INTEGER,
    "customer_state": PayloadSchemaType.KEYWORD,
    "customer_city": PayloadSchemaType.KEYWORD,
    "product_category": PayloadSchemaType.KEYWORD,
    "review_year": PayloadSchemaType.INTEGER,
    "review_month": PayloadSchemaType.INTEGER,
}
for field_name, field_type in fields_to_index.items():
    qdrant_client.create_payload_index(
    collection_name=collection_name,
    field_name=field_name,
    field_schema=field_type,
    )
    print(f"Index dibuat untuk field: {field_name}")

# Batch uploading logic using 100 entries per chunk loop
batch_size = 100
print("🚀 Initializing embedding runs and uploading vector points to Qdrant...")

for i in tqdm(range(0, len(records), batch_size)):
    chunk = records[i:i + batch_size]

    texts_to_embed = []
    payloads = []
    points = []

    for idx, row in enumerate(chunk):
        title_prefix = f"Title: {row['review_comment_title']}\n" if row['review_comment_title'] else ""
        full_context_text = f"{title_prefix}Message: {row['review_comment_message']}"
        texts_to_embed.append(full_context_text)
        
        # 📌 Your exact final metadata revision layout requested by the AI Engineer
        payloads.append({
            "review_score": int(row['review_score']),
            "customer_state": str(row['customer_state']),
            "customer_city": str(row['customer_city']),
            "product_category": str(row['product_category']),
            "review_year": int(row['review_year']),
            "review_month": int(row['review_month']),
            "text_content": full_context_text
        })
    
    try:
        response = openai_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts_to_embed
        )
        embeddings = [data.embedding for data in response.data]

        for j in range(len(chunk)):
            point_id = i + j  
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=embeddings[j],
                    payload=payloads[j]
                )
            )
            
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points
        )
    
    except Exception as e:
        print(f"\n❌ Execution failure encountered on batch range index {i}-{i+batch_size}: {e}")
        continue

print(f"\n✨ [FINAL RAG INGESTION COMPLETED] Collection '{collection_name}' is fully up to date and clean!")