import os
import json
import uuid
import time
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

# Initialize Pinecone
pinecone_key = os.environ.get("pinecone")
if not pinecone_key:
    print("Pinecone API key not found in environment!")
    exit(1)

pc = Pinecone(api_key=pinecone_key)

# We want an index name tailored for this chapter
index_name = "taxmate-chapter6a"

# Load JSONL file
data_file = "chapter6a.jsonl"
documents = []
with open(data_file, 'r', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            documents.append(json.loads(line))

print(f"Loaded {len(documents)} documents from {data_file}")

# Initialize NVIDIA Embeddings
embedder = NVIDIAEmbeddings(model="nvidia/nv-embedqa-e5-v5")

# Test embedding to get dimension
print("Testing embedding API to find dimension...")
try:
    test_embedding = embedder.embed_query("test")
    dimension = len(test_embedding)
    print(f"Embedding dimension: {dimension}")
except Exception as e:
    print(f"Error testing NVIDIA embedding: {e}")
    exit(1)

# Check and create Pinecone Index
if index_name not in pc.list_indexes().names():
    print(f"Creating Pinecone index '{index_name}' with dimension {dimension}...")
    pc.create_index(
        name=index_name,
        dimension=dimension,
        metric="cosine",
        spec=ServerlessSpec(
            cloud="aws",
            region="us-east-1"
        )
    )
    # wait for index to be ready
    while not pc.describe_index(index_name).status['ready']:
        time.sleep(1)
        print("Waiting for index to be ready...")

index = pc.Index(index_name)

# Process and upsert documents
batch_size = 32
vectors_to_upsert = []

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=200,
    length_function=len,
    is_separator_regex=False,
)

print("Generating embeddings and upserting...")
for i, doc in enumerate(documents):
    # Prepare text for embedding
    title = doc.get("title", "")
    keywords = ", ".join(doc.get("keywords", []))
    full_text = doc.get("full_text", "")
    
    # Split text if it's too long. We prepend title and keywords to each chunk to keep context.
    chunks = text_splitter.split_text(full_text)
    
    for chunk_idx, chunk in enumerate(chunks):
        text_content = f"Title: {title}\nKeywords: {keywords}\n\n{chunk}"
        
        try:
            embedding = embedder.embed_query(text_content)
            
            # Prepare metadata for Pinecone
            metadata = {
                "section_id": doc.get("section_id", ""),
                "title": title,
                "active": doc.get("active", True),
                "max_limit_inr": doc.get("max_limit_inr", -1) if doc.get("max_limit_inr") is not None else -1,
                "text": text_content[:5000], # Pinecone max metadata is 40kb per vector, truncate safely
                "chunk_index": chunk_idx
            }
            
            base_id = doc.get('section_id', str(uuid.uuid4()))
            vector_id = f"sec_{base_id}_chunk_{chunk_idx}"
            
            vectors_to_upsert.append({
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            })
            
            if len(vectors_to_upsert) >= batch_size:
                print(f"Upserting batch of {len(vectors_to_upsert)} vectors...")
                index.upsert(vectors=vectors_to_upsert)
                vectors_to_upsert = []
                
        except Exception as e:
            print(f"Error processing document {doc.get('section_id')} chunk {chunk_idx}: {e}")

# Upsert remaining
if vectors_to_upsert:
    print(f"Upserting final batch of {len(vectors_to_upsert)} vectors...")
    index.upsert(vectors=vectors_to_upsert)

print("Done! Vectors upserted to Pinecone successfully.")
