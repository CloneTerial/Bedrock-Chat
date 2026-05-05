import asyncio
import os
import json
import aiohttp
import numpy as np
import faiss
from services.rag import get_embedding

async def search_knowledge_base(inp: dict):
    """Search for relevant chunks in the FAISS vector database."""
    KB_DIR = "knowledge_base"
    query = inp.get("query", "")
    index_path = os.path.join(KB_DIR, "index.faiss")
    meta_path = os.path.join(KB_DIR, "metadata.json")
    
    if not os.path.exists(index_path):
        return {"error": "Knowledge base is empty. Please upload files first."}
        
    q_emb = get_embedding(query)
    q_emb_np = q_emb.reshape(1, -1)
    
    index = faiss.read_index(index_path)
    k = 4
    D, I = index.search(q_emb_np, k)
    
    with open(meta_path, "r") as f:
        metadata = json.load(f)
        
    results = []
    for i in I[0]:
        if i != -1 and i < len(metadata):
            results.append(metadata[i])
    
    return {"query": query, "results": results}

async def tavily_search(inp: dict):
    """Perform a web search using Tavily API."""
    query = inp.get("query", "")
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"error": "TAVILY_API_KEY not found in .env"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": 3
                },
                timeout=15
            ) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    return {"error": f"Tavily API Error (HTTP {resp.status}): {err_text}"}
                
                data = await resp.json()
        
        results = []
        if data.get("answer"):
            results.append(f"Tavily Answer: {data['answer']}")
        for res in data.get("results", []):
            results.append(f"Source ({res['url']}):\n{res['content']}")
        
        return {"query": query, "results": "\n\n".join(results)}
    except Exception as e:
        import traceback
        err_detail = traceback.format_exc()
        err_msg = str(e) if str(e) else repr(e)
        return {"error": f"Web search failed: {err_msg}", "detail": err_detail}

async def run_asymptote(inp: dict):
    """Execute specialized financial scripts from the Asymptote project."""
    tool = inp.get("tool", "").lower()
    args = inp.get("args", "")
    
    tool_map = {
        "binance": "cli_binance.py",
        "onchain": "cli_onchain.py",
        "coingecko": "cli_coingecko.py",
        "news": "cli_news.py",
        "macro": "cli_macro.py",
        "sec": "cli_sec.py"
    }
    
    script = tool_map.get(tool)
    if not script:
        return {"error": f"Unknown tool '{tool}'. Available: {list(tool_map.keys())}"}
    
    asymptote_path = r"E:\workflow\Asymptote"
    python_exe = os.path.join(asymptote_path, "venv", "Scripts", "python.exe")
    script_path = os.path.join("cli_tools", script)
    
    full_command = f'cd /d {asymptote_path} && "{python_exe}" {script_path} {args}'
    
    def sync_run():
        import subprocess
        return subprocess.run(
            full_command,
            shell=True,
            capture_output=True,
            text=False
        )

    try:
        result = await asyncio.to_thread(sync_run)
        
        return {
            "tool": tool,
            "command": full_command,
            "stdout": result.stdout.decode(errors="replace").strip(),
            "stderr": result.stderr.decode(errors="replace").strip(),
            "returncode": result.returncode
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        err_msg = str(e) if str(e) else repr(e)
        return {
            "error": f"Failed to execute Asymptote (Threaded): {err_msg}", 
            "command": full_command,
            "detail": error_detail
        }
