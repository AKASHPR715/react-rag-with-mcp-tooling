import os
import sys
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Union, Optional, AsyncIterator

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.output_parsers import BaseOutputParser
from langchain_pinecone import PineconeVectorStore
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings, ChatNVIDIA
from langchain.agents import AgentExecutor, create_react_agent
from langchain import hub
from logging.handlers import RotatingFileHandler

# Load environment variables
load_dotenv()

# ============================================================
# Logging Setup
# ============================================================
def setup_advisor_logger():
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tax_advisor.log"
    
    logger = logging.getLogger("tax_advisor")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        fh = RotatingFileHandler(
            log_file, 
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=2,
            encoding="utf-8"
        )
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(fh)
        
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("ADVISOR: %(message)s"))
        logger.addHandler(ch)
    
    return logger

advisor_logger = setup_advisor_logger()

# ============================================================
# Configuration & Constants
# ============================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
PINECONE_API_KEY = os.getenv("pinecone") or os.getenv("PINECONE_API_KEY")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

INDEX_NAME = "taxmate-chapter6a"
EMBEDDING_MODEL = "nvidia/nv-embedqa-e5-v5"

# Fallback imports for other services
try:
    from app.services.extraction_tool.rag_tool.graphdb import query_tax_graph
    # db_helpers seems missing, but I'll update it just in case or let it fallback
    # from app.services.db_helpers import get_sync_db
    from bson import ObjectId
except ImportError:
    @tool
    def query_tax_graph(query: str) -> str:
        """Fallback tool if graphdb is not available."""
        return "Graph database query is currently unavailable."
    
    def get_sync_db(): return None
    class ObjectId: pass

from tavily import TavilyClient
tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

# ============================================================
# Cloud Components (Pinecone & NVIDIA)
# ============================================================

# Initialize Embeddings
embeddings = NVIDIAEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=NVIDIA_API_KEY
)

# Initialize Vector Store
try:
    if PINECONE_API_KEY:
        vectorstore = PineconeVectorStore(
            index_name=INDEX_NAME,
            embedding=embeddings,
            pinecone_api_key=PINECONE_API_KEY
        )
        advisor_logger.info("Pinecone Vector Store initialized successfully.")
    else:
        vectorstore = None
        advisor_logger.warning("PINECONE_API_KEY missing. Vector store unavailable.")
except Exception as e:
    vectorstore = None
    advisor_logger.error(f"Failed to initialize Pinecone: {e}")

# ============================================================
# Agent Tools
# ============================================================

@tool
def retrieve_tax_laws(query: str) -> str:
    """
    Search the Indian Income Tax Act (focusing on Chapter VI-A deductions like 80C, 80D, 80CCD, etc.).
    Use this to find specific rules, limits, and eligibility criteria for tax savings.
    """
    if not vectorstore:
        return "Tax law database is currently unavailable (check API keys)."
    
    try:
        advisor_logger.info(f"RAG Retrieval for: {query}")
        docs = vectorstore.similarity_search(query, k=4)
        if not docs:
            return "No specific tax laws found for this query."
        
        results = []
        for doc in docs:
            results.append(f"Source: {doc.metadata.get('title', 'Tax Provision')}\nContent: {doc.page_content}")
        
        return "\n\n---\n\n".join(results)
    except Exception as e:
        advisor_logger.error(f"Retrieval error: {e}")
        return f"Error retrieving tax laws: {e}"

@tool
def search_latest_tax_updates(query: str) -> str:
    """
    Search the web for the absolute latest tax updates, budget 2024/2025 notifications, 
    or clarifications that might not be in the static database.
    """
    if not tavily_client:
        return "Web search is unavailable (Missing API Key)."
        
    try:
        advisor_logger.info(f"Web Search for: {query}")
        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            include_answer=True,
            max_results=3
        )
        answer = response.get("answer", "No clear answer found.")
        sources = "\n".join(f"- {res['url']}" for res in response.get("results", [])[:3])
        return f"{answer}\n\nSources:\n{sources}"
    except Exception as e:
        return f"Web search failed: {str(e)}"

# ============================================================
# Agent Reasoning Logic
# ============================================================

class RobustReActOutputParser(BaseOutputParser):
    def parse(self, text: str) -> Union[AgentAction, AgentFinish]:
        if "Final Answer:" in text:
            output = text.split("Final Answer:")[-1].strip()
            return AgentFinish(return_values={"output": output}, log=text)
            
        regex = r"Action: (.*?)\nAction Input: (.*)"
        match = re.search(regex, text, re.DOTALL)
        
        if match:
            action = match.group(1).strip()
            action_input = match.group(2).strip(" ").strip('"')
            return AgentAction(tool=action, tool_input=action_input, log=text)
            
        return AgentFinish(return_values={"output": text}, log=text)

def strip_markdown(text: str) -> str:
    """Clean up markdown for frontend display."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    # text = re.sub(r'(?<!\n)\*(.+?)\*', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    return text

# Initialize LLM
llm = None
if NVIDIA_API_KEY:
    llm = ChatNVIDIA(
        model="meta/llama-3.1-70b-instruct",
        api_key=NVIDIA_API_KEY,
        temperature=0,
        max_tokens=4000,
    ).bind(stop=["\nObservation:", "Observation:"])

# Setup Agent
tools = [retrieve_tax_laws, search_latest_tax_updates, query_tax_graph]
prompt = hub.pull("hwchase17/react")

agent_executor = None
if llm:
    agent = create_react_agent(llm, tools, prompt, output_parser=RobustReActOutputParser())
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10,
        early_stopping_method="force"
    )

def classify_query(question: str) -> str:
    """
    Classifies the query as 'tax' or 'casual'.
    Uses a small prompt to NVIDIA NIM for better accuracy.
    """
    if not llm:
        return "tax"  # Default to tax if LLM not ready
        
    classification_prompt = (
        "Classify the following user query into one of two categories: 'tax' or 'casual'.\n"
        "A 'tax' query is about Indian income tax, deductions, sections like 80C, 80D, NPS, budget updates, or tax planning.\n"
        "A 'casual' query is anything else like greetings, general knowledge not related to tax, personal questions, or casual chat.\n"
        f"Query: {question}\n"
        "Classification (respond ONLY with the word 'tax' or 'casual'):"
    )
    
    try:
        response = llm.invoke(classification_prompt)
        result = response.content.strip().lower()
        if "casual" in result:
            return "casual"
        return "tax"
    except Exception:
        return "tax" # Fallback to tax to be safe

def get_tax_advice(question: str, user_id: str = None) -> str:
    """Main entry point for getting tax advice."""
    if not agent_executor:
        return "Tax Advisor Agent not initialized. Check configuration."
    
    # 1. Classify Query
    intent = classify_query(question)
    if intent == "casual":
        advisor_logger.info(f"Casual query detected: {question}")
        return "I am a tax advisor. This query does not seem related to Indian taxes. Please ask me something about tax savings, deductions, or the Income Tax Act."

    advisor_logger.info(f"Tax advice request (Reasoning): {question} (User: {user_id})")
    
    # Load user context if available
    context_str = ""
    if user_id:
        try:
            db = get_sync_db()
            if db:
                # Simple fetch for context
                f16 = db.form16_part_bs.find_one(
                    {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]},
                    sort=[("created_at", -1)]
                )
                if f16:
                    context_str = (
                        f"\nUser Financial Context:\n"
                        f"- Total Income: ₹{f16.get('gross_total_income', 0):,.2f}\n"
                        f"- Current Taxable: ₹{f16.get('taxable_income', 0):,.2f}\n"
                    )
        except Exception as e:
            advisor_logger.warning(f"Ctx fetch failed: {e}")

    full_prompt = f"User Question: {question}\n{context_str}\nProvide concise, strategic tax advice using your tools."
    
    try:
        response = agent_executor.invoke({"input": full_prompt})
        output = response.get("output", "I'm sorry, I couldn't formulate advice at this time.")
        return strip_markdown(output)
    except Exception as e:
        advisor_logger.error(f"Agent failed: {e}")
        # Secondary fallback to direct search
        fallback = search_latest_tax_updates.invoke(question)
        return f"Agent reasoning limit reached. Direct search result:\n\n{strip_markdown(fallback)}"

async def get_user_context_async(user_id: str) -> str:
    """Helper to fetch user context asynchronously."""
    if not user_id:
        return ""
    try:
        # Since the current environment might use motor or pymongo, 
        # for now, we'll use a simplified version or just stick to the sync one if needed.
        # However, to be truly async-friendly, we'd want motor. 
        # I'll use the sync one wrapped if motor isn't here, but usually, it's better to keep it light.
        db = get_sync_db()
        if db:
            f16 = db.form16_part_bs.find_one(
                {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]},
                sort=[("created_at", -1)]
            )
            if f16:
                return (
                    f"\nUser Financial Context:\n"
                    f"- Total Income: ₹{f16.get('gross_total_income', 0):,.2f}\n"
                    f"- Current Taxable: ₹{f16.get('taxable_income', 0):,.2f}\n"
                )
    except Exception as e:
        advisor_logger.warning(f"Ctx fetch failed: {e}")
    return ""

async def stream_tax_advice(question: str, user_id: str = None) -> AsyncIterator[Dict[str, Any]]:
    """Streaming entry point for getting tax advice with thinking steps."""
    if not agent_executor:
        yield {"error": "Tax Advisor Agent not initialized."}
        return

    # 1. Classify Query (kept sync for simplicity as it's fast)
    intent = classify_query(question)
    if intent == "casual":
        yield {"answer": "I am a tax advisor. This query does not seem related to Indian taxes. Please ask me something about tax savings, deductions, or the Income Tax Act."}
        return

    advisor_logger.info(f"Stream tax advice request: {question}")
    context_str = await get_user_context_async(user_id)
    full_prompt = f"User Question: {question}\n{context_str}\nProvide concise, strategic tax advice using your tools."

    try:
        # Using astream_events (v2) to capture tool starts (thinking) and final output
        async for event in agent_executor.astream_events(
            {"input": full_prompt},
            version="v2",
        ):
            kind = event["event"]
            
            # Identify tool execution (Thinking steps)
            if kind == "on_tool_start":
                tool_name = event["name"]
                tool_input = event["data"].get("input")
                yield {"thinking": f"Searching for: {tool_input} using {tool_name}..."}
            
            # Identify final output chunks
            elif kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    yield {"answer_chunk": content}
            
            # Alternative for non-streaming models or final aggregation
            elif kind == "on_chain_end":
                if event["name"] == "AgentExecutor":
                    output = event["data"]["output"].get("output", "")
                    if output:
                        # If we haven't streamed chunks, or as a final check
                        # Note: we strip markdown at the end in the UI ideally, but we can do it here too
                        # yield {"answer": strip_markdown(output)}
                        pass

    except Exception as e:
        advisor_logger.error(f"Streaming Agent failed: {e}")
        yield {"error": f"I encountered an error while processing: {str(e)}"}


# MCP Integration
# (Removed old app.mcp_app imports as it is missing)

if __name__ == "__main__":
    # Quick test
    print(get_tax_advice("What is the limit for 80C?"))