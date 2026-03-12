import sys
import os
from pathlib import Path

# Add project root to sys.path to support 'app.' absolute imports
root_path = str(Path(__file__).resolve().parent)
if root_path not in sys.path:
    sys.path.append(root_path)

from fastmcp import FastMCP
from app.services.rag_tool.tax_advisor_service import get_tax_advice
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("TaxMate Advisor")

@mcp.tool()
def get_strategic_tax_advice(question: str, user_id: str = None) -> str:
    """
    Asks the AI Tax Advisor for strategic tax saving advice.
    The advisor uses RAG (Pinecone) and reasoning (NVIDIA NIM) to provide tailored answers.
    
    Args:
        question: The tax-related question or request for advice.
        user_id: Optional ID of the user to fetch financial context if available.
    """
    try:
        # get_tax_advice already handles classification and RAG
        return get_tax_advice(question, user_id)
    except Exception as e:
        return f"Error getting tax advice: {str(e)}"

import sys

if __name__ == "__main__":
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]
    
    if transport == "sse":
        print("Starting MCP server with SSE transport on http://localhost:8001")
        mcp.run(transport="sse", port=8001)
    else:
        print("Starting MCP server with 'stdio' transport.")
        print("NOTE: This mode is for MCP Clients (like Claude Desktop). The terminal will appear 'stuck' as it waits for input.")
        print("To test interactively in your browser, run: python3 mcp_server.py --transport sse")
        mcp.run(transport="stdio")
