"""
Tax-tool module – exposes @tool retrieve_context
Uses persistent Qdrant + nomic-embed-text via langchain-ollama
"""
import pickle
from typing import Any, List
from qdrant_client import models 
from langchain_ollama import OllamaEmbeddings  
from qdrant_client.http.models import FusionQuery, Fusion
import numpy as np
from pydantic import ConfigDict        # <= new import
from langchain_core.tools import tool
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    SparseVector, Filter, FieldCondition, MatchValue, MatchAny
)
from pydantic import Field

from pathlib import Path

# ---------- config ----------
COLLECTION_NAME = "chapter_vi_a_langchain"
TOP_K = 6
# Dynamic path resolution:
# Start from this file (__file__), go up to app, then to data/extracted
APP_ROOT = Path(__file__).resolve().parent.parent
VECTORIZER_PKL = APP_ROOT / "data" / "extracted" / "vi_a_vectorizer.pkl"
PERSIST_DIR = str(APP_ROOT / "qdrant_storage")
EMBEDDING_MODEL = "nomic-embed-text"   # << nomic via Ollama
# ----------------------------

# ---- load once ----
try:
    with open(VECTORIZER_PKL, "rb") as f:
        vectorizer = pickle.load(f)
except Exception as e:
    print(f"Warning: Could not load vectorizer from {VECTORIZER_PKL}: {e}")
    vectorizer = None

# ---- retriever ----
class HybridQdrantRetriever(BaseRetriever):
    client: Any = Field(...)
    embeddings: Any = Field(...)
    vectorizer: Any = Field(...)
    top_k: int = TOP_K
    user_type: str = "individual"
    model_config = ConfigDict(arbitrary_types_allowed=True)  

   

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun = None
    ) -> List[Document]:
        dense = self.embeddings.embed_query(query)
        if self.vectorizer:
            q_vec = self.vectorizer.transform([query])
            sparse = SparseVector(
                indices=q_vec.nonzero()[1].astype(np.uint32).tolist(),
                values=q_vec.data.astype(np.float32).tolist()
            )
        else:
            print("Warning: Vectorizer not loaded. Skipping sparse retrieval...")
            sparse = SparseVector(indices=[], values=[])

        must = [FieldCondition(key="active", match=MatchValue(value=True))]
        if self.user_type:
            must.append(
                FieldCondition(key="applicable_to", match=MatchAny(any=[self.user_type, "all"]))
            )

        try:
            res = self.client.query_points(
                collection_name=COLLECTION_NAME,
                prefetch=[
                    models.Prefetch(query=dense, using="dense", limit=self.top_k * 2),
                    models.Prefetch(query=sparse, using="sparse", limit=self.top_k * 2),
                ],
                # query={"fusion": {"rrf": {}}},
                
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                query_filter=Filter(must=must),
                limit=self.top_k,
                with_payload=True,
            )

            docs = []
            for hit in res.points:
                p = hit.payload
                parts = [f"Section {p.get('section_id', 'N/A')}: {p.get('title', 'N/A')}"]
                if p.get("max_limit_inr"):
                    parts.append(f"Max Limit: ₹{p['max_limit_inr']:,}")
                if p.get("conditions"):
                    parts.append("\nConditions:")
                    for c in p["conditions"]:
                        parts.append(f"  • {c}")
                if p.get("mutual_exclusions"):
                    parts.append(f"Cannot be claimed with: {', '.join(p['mutual_exclusions'])}")
                if p.get("co_claimable_with"):
                    parts.append(f"Can be claimed with: {', '.join(p['co_claimable_with'])}")
                if p.get("full_text"):
                    txt = p["full_text"]
                    if len(txt) > 2000:
                        txt = txt[:2000] + " ...[truncated]"
                    parts.append(f"\nLegal Text:\n{txt}")
                docs.append(Document(page_content="\n".join(parts), metadata=p))
            return docs
            
        except Exception as e:
            # Fallback if collection doesn't exist or DB is down
            print(f"Vector DB Retrieval Warning: {e}")
            return [Document(page_content=f"Note: Local tax law database (Section 80C, etc.) is currently unavailable. Error: {str(e)[:50]}...", metadata={"source": "system"})]

import os
# ---- instantiate ----
qdrant_client = QdrantClient(path=PERSIST_DIR)
ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=ollama_url)
retriever = HybridQdrantRetriever(
    client=qdrant_client,
    embeddings=embeddings,
    vectorizer=vectorizer,
    top_k=TOP_K
)

# ---- tool ----
@tool
def retrieve_context(query: str) -> str:
    """
    Look up the Indian Income Tax Act (Chapter VI-A).
    Input: a specific question about sections like 80C, 80CCD(1B), deduction limits, or eligibility.
    """
    docs = retriever.invoke(query)
    return "\n\n".join(doc.page_content for doc in docs)

tools = [retrieve_context]

# MCP Tool Definition removed as app/mcp_app.py is missing.
