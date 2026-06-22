import os
import dotenv
import pandas as pd
from tqdm import tqdm
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models
from config import *

dotenv.load_dotenv()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not all([OPENAI_KEY, QDRANT_URL, QDRANT_API_KEY]):
    print("❌ Error: Missing required credentials in environment variables.")
    print("💡 Ensure OPENAI_API_KEY, QDRANT_URL, and QDRANT_API_KEY are configured.")

openai_client = OpenAI(api_key=OPENAI_KEY)
qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else '.'
csv_path = os.path.join(script_dir, 'olist_order_reviews_dataset.csv')

if not os.path.exists(csv_path):
    csv_path = 'olist_order_reviews_dataset.csv'

print(f"📥 Loading source reviews dataset from: {csv_path}")
df = pd.read_csv(csv_path)

df = df[df['review_comment_message'].notna() & (df['review_comment_message'].str.strip() != '')].copy()

df['review_comment_title'] = df['review_comment_title'].fillna('')

print(f"📋 Found {len(df)} eligible review messages to vectorize.")

collection_name = QDRANT_COLLECTION_NAME
print(f"⚙️ Setting up collection '{collection_name}' in Qdrant Cloud...")

if collection_name in qdrant_client.get_collections().collections:
    print(f"⚠️ Collection '{collection_name}' already exists. Recreating it to ensure a clean state.")

qdrant_client.recreate_collection(
    collection_name=collection_name,
    vectors_config=models.VectorParams(
        size=3072, 
        distance=models.Distance.COSINE
    )
)
batch_size = 100 
records = df.to_dict('records')

print("🚀 Extracting embeddings and streaming records into Qdrant Cloud...")

for i in tqdm(range(0, len(records), batch_size)):
    chunk = records[i:i + batch_size]

    texts_to_embed = []
    payloads = []
    points = []

    for idx, row in enumerate(chunk):
        title_prefix = f"Title: {row['review_comment_title']}\n" if row['review_comment_title'] else ""
        full_context_text = f"{title_prefix}Message: {row['review_comment_message']}"
        texts_to_embed.append(full_context_text)
        
        payloads.append({
            "review_id": str(row['review_id']),
            "order_id": str(row['order_id']),
            "review_score": int(row['review_score']),
            "review_comment_title": str(row['review_comment_title']),
            "review_comment_message": str(row['review_comment_message']),
            "review_creation_date": str(row['review_creation_date']),
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

print(f"\n✨ [RAG INGESTION COMPLETED] Collection '{collection_name}' successfully compiled and active!")