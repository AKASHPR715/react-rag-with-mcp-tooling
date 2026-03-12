 # TaxMate v2 - AI-Powered Tax Advisor

TaxMate v2 is a modern, agentic tax advisory system designed to help Indian taxpayers navigate the complexities of the Income Tax Act. It leverages a cloud-native architecture for retrieval, reasoning, and tool integration.

## 🚀 Features

- **Agentic RAG**: Uses a ReAct reasoning agent to intelligently query a Pinecone Cloud vector store containing the Indian Income Tax Act (focusing on Chapter VI-A deductions).
- **NVIDIA NIM Integration**:
  - **Embeddings**: High-quality vector representation using `nv-embedqa-e5-v5`.
  - **Reasoning**: Advanced LLM reasoning powered by `meta/llama-3.1-70b-instruct`.
- **Query Classification**: Automatically detects "casual" queries to bypass expensive RAG operations, providing immediate context-aware responses.
- **FastAPI Endpoint**: Exposed via a high-performance REST API for web and mobile integration.
- **FastMCP Server**: Natively supports the Model Context Protocol (MCP), allowing the advisor to be used as a tool in Claude Desktop, VS Code, and other MCP-enabled environments.
- **Knowledge Graph Integration**: Integrated with Neo4j to answer complex questions about relationships between tax sections and rules.
- **Web Fallback**: Real-time web search via Tavily for the latest budget updates and notifications.

## 🛠️ Tech Stack

- **Framework**: FastAPI (API), FastMCP (MCP)
- **AI/LLM**: NVIDIA NIM (Meta Llama 3.1)
- **Vector DB**: Pinecone Cloud
- **Graph DB**: Neo4j
- **Agent Orchestration**: LangChain (React Agent)
- **Environment**: Python 3.10+

## ⚙️ Setup Instructions

### 1. Prerequisites
Ensure you have Python 3.10+ and a virtual environment set up.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables
Create a `.env` file in the root directory and add the following:

```env
NVIDIA_API_KEY=your_nvidia_key
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=taxmate
TAVILY_API_KEY=your_tavily_key
NEO4J_URI=your_neo4j_uri
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

### 3. Running the Service

#### FastAPI Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- **Endpoint**: `POST /api/tax-advisor/ask`
- **Body**: `{"question": "How can I save tax under 80C?"}`

#### MCP Server
```bash
python3 mcp_server.py
```
This starts the MCP server in `stdio` mode, ready to be added to your MCP config.

## 📁 Project Structure

- `app/main.py`: FastAPI entry point.
- `app/services/tax_advisor_service.py`: Core agentic reasoning and RAG logic.
- `mcp_server.py`: FastMCP server implementation.
- `embed_to_pinecone.py`: Utility script for ingesting data into Pinecone.

## 🔒 License
MIT License.

start mcp server = python3 mcp_server.py --transport sse
swagger like gui = npx @modelcontextprotocol/inspector --transport sse --server-url http://localhost:8001/sse