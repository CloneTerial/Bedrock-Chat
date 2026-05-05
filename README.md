# Bedrock Chat: Autonomous AI Developer & Macro Analyst

Bedrock Chat is an interactive AI platform that combines the power of Claude 4.5/Opus/Sonnet models (via AWS Bedrock) with an Autonomous Agent system. Designed for developers and financial analysts, this application enables AI to interact directly with your file system, perform real-time market research, and execute automated macroeconomic analysis.

## System Compatibility

**Important:** Currently, this project is exclusively designed for **Windows OS**.
- The tool execution logic uses Windows-specific shell commands (e.g., `cd /d`).
- Linux/macOS support is not yet implemented.

## Key Features

- **Multi-Model Support**: Seamless integration with AWS Bedrock (Claude series) and OpenAI Compatible APIs (DeepSeek, Qwen).
- **Autonomous Tool Suite**:
  - **File System**: Read, write, and perform surgical code patching.
  - **Browser Automation**: Internet browsing using Playwright (Headless Chromium).
  - **Financial Intelligence**: Integration with the Asymptote workflow for Binance data, On-chain BTC metrics, Coingecko, and SEC news.
  - **Macro Analyzer**: Fetch data from FRED, World Bank, and IMF for global economic analysis.
- **Local RAG (Retrieval-Augmented Generation)**: Upload documents (PDF/Text) and get answers based on your local data using the FAISS vector store.
- **SSE Streaming**: Responsive UI with real-time text streaming and tool execution logs.
- **Long-term Memory**: Persistent memory system to maintain important context across different conversations.

## Project Architecture

```text
bedrock-chat/
├── providers/        # AI Providers (Bedrock, OpenAI Compat)
├── services/         # Storage & RAG Vector Engine
├── static/           # Frontend (Vanilla JS + CSS)
├── tools/            # Autonomous Tool Registry
├── chats/            # Local conversation storage (JSON)
├── knowledge_base/   # FAISS Vector Index
└── server.py         # FastAPI Backend
```

## Installation Guide

### 1. Clone the Repository

```bash
git clone https://github.com/username/bedrock-chat.git
cd bedrock-chat
```

### 2. Environment Setup

Using a Virtual Environment is recommended:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. API Key Configuration

Copy `.env-example` to `.env` and fill in your credentials:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
TAVILY_API_KEY=your_tavily_key
QWEN_API_KEY=your_qwen_key
FRED_API_KEY=your_fred_key
```

### 4. Browser Tool Setup

The application requires Playwright for web browsing capabilities:

```bash
playwright install chromium
```

## How to Run

Start the server using Uvicorn:

```bash
python server.py
```

Access the web interface at: `http://localhost:8000`

## AI Usage Examples

You can issue complex commands such as:

- _"Read server.py and create unit tests for the /api/chat endpoint."_
- _"Check the current BTC price on Binance and compare it with the latest news sentiment."_
- _"Upload this annual report PDF and summarize the key risk factors."_
- _"Run the macro analyzer for US unemployment data from FRED for the last 5 years."_

## Security Notes

- This application has **full access to the shell and file system** (via `execute_shell` and `write_file`). It should only be used in a secure environment (sandbox or local development).

## License

MIT License - See [LICENSE](LICENSE) for more details.
