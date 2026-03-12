import sys
import os
from pathlib import Path

# Add project root to sys.path to support 'app.' absolute imports
root_path = str(Path(__file__).resolve().parent.parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json
from app.services.extraction_tool.rag_tool.tax_advisor_service import get_tax_advice, stream_tax_advice
import uvicorn

app = FastAPI(title="TaxMate Advisor API")

# Load FRONTEND_URL from environment
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TaxQuery(BaseModel):
    question: str
    user_id: Optional[str] = None

class TaxResponse(BaseModel):
    question: str
    advice: str

@app.post("/api/tax-advisor/ask", response_model=TaxResponse)
async def ask_tax_advisor(query: TaxQuery):
    """
    Endpoint to get AI tax advice.
    """
    try:
        advice = get_tax_advice(query.question, query.user_id)
        return TaxResponse(question=query.question, advice=advice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(query: TaxQuery):
    """
    Streaming endpoint for chat with thinking steps.
    """
    async def event_generator():
        try:
            async for chunk in stream_tax_advice(query.question, query.user_id):
                # Yield as JSON strings for the frontend to parse
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            error_msg = {"error": str(e)}
            yield f"data: {json.dumps(error_msg)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

