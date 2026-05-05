import json
import asyncio
import os
import re
import uuid
import aiohttp
from typing import AsyncGenerator
from providers.base import BaseProvider
from tools import exec_tool

class OpenAICompatProvider(BaseProvider):
    """
    Provider for OpenAI-compatible APIs (e.g., DeepSeek, Qwen).
    Handles streaming chat and robust tool-call parsing from model output.
    """
    def sse(self, data: dict) -> str:
        """Format data as Server-Sent Event (SSE)."""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream_chat(self, req, conv, sys_prompt, mcfg, use_tools) -> AsyncGenerator[str, None]:
        """Stream completions and handle potential tool calls in multiple formats."""
        from config import TOOLS
        msgs = conv["messages"]
        model_id = req.model or mcfg.get("model_id")
        temp = req.temperature if req.temperature is not None else 0.7
        max_tok = req.max_tokens or 4096
        
        t_in = 0
        t_out = 0

        openai_tools = []
        if use_tools:
            for t in TOOLS:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": t["toolSpec"]["name"],
                        "description": t["toolSpec"]["description"],
                        "parameters": t["toolSpec"]["inputSchema"]["json"]
                    }
                })

        for _ in range(50):
            oai_msgs = [{"role": "system", "content": sys_prompt}]
            for m in msgs:
                if m["role"] == "user":
                    if any("toolResult" in b for b in m["content"]):
                        for b in m["content"]:
                            if "toolResult" in b:
                                tr = b["toolResult"]
                                oai_msgs.append({
                                    "role": "tool",
                                    "tool_call_id": tr["toolUseId"],
                                    "content": tr["content"][0]["text"]
                                })
                    else:
                        text_content = "".join([b.get("text", "") for b in m["content"] if "text" in b])
                        oai_msgs.append({"role": "user", "content": text_content})
                        
                elif m["role"] == "assistant":
                    text_content = "".join([b.get("text", "") for b in m["content"] if "text" in b])
                    oai_msg = {"role": "assistant", "content": text_content}
                    
                    tool_calls = []
                    for b in m["content"]:
                        if "toolUse" in b:
                            tu = b["toolUse"]
                            tool_calls.append({
                                "id": tu["toolUseId"],
                                "type": "function",
                                "function": {
                                    "name": tu["name"],
                                    "arguments": json.dumps(tu["input"])
                                }
                            })
                    if tool_calls:
                        oai_msg["tool_calls"] = tool_calls
                    oai_msgs.append(oai_msg)
            
            try:
                headers = {
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "true" 
                }
                api_key_env = mcfg.get("api_key_env")
                if api_key_env and os.getenv(api_key_env):
                    headers["Authorization"] = f"Bearer {os.getenv(api_key_env)}"

                payload = {
                    "model": model_id,
                    "messages": oai_msgs,
                    "temperature": temp,
                    "max_tokens": max_tok,
                    "stream": True
                }
                if use_tools and openai_tools:
                    payload["tools"] = openai_tools

                base_url = mcfg.get("base_url", "").rstrip("/")
                txt = ""
                tool_calls_dict = {}
                stop_reason = "stop"

                async with aiohttp.ClientSession() as session:
                    async with session.post(f"{base_url}/chat/completions", headers=headers, json=payload) as resp:
                        if resp.status != 200:
                            err_body = await resp.text()
                            raise Exception(f"HTTP {resp.status}: {err_body}")
                            
                        async for line in resp.content:
                            line = line.decode('utf-8').strip()
                            if line.startswith("data: ") and line != "data: [DONE]":
                                try:
                                    chunk = json.loads(line[6:])
                                    choice = chunk["choices"][0]
                                    delta = choice.get("delta", {})
                                    
                                    if "content" in delta and delta["content"]:
                                        txt += delta["content"]
                                        t_out += 1 
                                        yield self.sse({"type": "text", "content": delta["content"]})
                                        
                                    if "tool_calls" in delta and delta["tool_calls"]:
                                        for tc in delta["tool_calls"]:
                                            idx = tc["index"]
                                            if idx not in tool_calls_dict:
                                                tool_calls_dict[idx] = {"id": tc.get("id"), "name": "", "arguments": ""}
                                            if "function" in tc:
                                                f = tc["function"]
                                                if "name" in f and f["name"]:
                                                    tool_calls_dict[idx]["name"] += f["name"]
                                                    yield self.sse({"type": "tool_start", "name": tool_calls_dict[idx]["name"]})
                                                if "arguments" in f and f["arguments"]:
                                                    tool_calls_dict[idx]["arguments"] += f["arguments"]
                                    if choice.get("finish_reason"):
                                        stop_reason = choice["finish_reason"]
                                except: pass

                a_blocks = []
                temp_tool_calls = []
                
                NAME_MAP = {
                    "read_file": "read_file", "read file": "read_file",
                    "get_datetime": "get_datetime", "datetime": "get_datetime", "date_time": "get_datetime", "time": "get_datetime",
                    "calculator": "calculator", "calc": "calculator",
                    "run_python": "run_python", "python_executor": "run_python", "python": "run_python", "python executor": "run_python",
                    "tavily_search": "tavily_search", "tavily": "tavily_search", "search": "tavily_search", "web_search": "tavily_search",
                    "execute_shell": "execute_shell", "shell": "execute_shell", "terminal": "execute_shell", "bash": "execute_shell",
                    "browser_playwright": "browser_playwright", "browser": "browser_playwright", "playwright": "browser_playwright",
                    "search_knowledge_base": "search_knowledge_base", "knowledge_base": "search_knowledge_base", "rag": "search_knowledge_base",
                    "run_asymptote": "run_asymptote", "asymptote": "run_asymptote",
                    "run_macro_analyzer": "run_macro_analyzer", "macro_analyzer": "run_macro_analyzer"
                }

                full_raw_txt = txt
                
                # 1. Parsing format <tool_call>
                for match in re.finditer(r'<tool_call>(.*?)(?=<tool_call>|</think>|</tool_call>|$)', full_raw_txt, re.DOTALL | re.IGNORECASE):
                    raw_content = match.group(1).strip()
                    if not raw_content: continue
                    
                    func_match = re.search(r'<function=([^>]+)>(?:.*?<arguments>(.*?)</arguments>)?', raw_content, re.DOTALL | re.IGNORECASE)
                    if func_match:
                        t_name = func_match.group(1).strip().lower().replace("_api", "")
                        t_args_raw = func_match.group(2) or "{}"
                        try: t_args = json.loads(t_args_raw.strip())
                        except: t_args = {"input": t_args_raw.strip()}
                        temp_tool_calls.append({"id": f"cx_{uuid.uuid4().hex[:6]}", "name": NAME_MAP.get(t_name, t_name), "input": t_args})
                        continue

                    try:
                        json_str_match = re.search(r'(\{.*\}|\[.*\])', raw_content, re.DOTALL)
                        if json_str_match:
                            json_str = json_str_match.group(1)
                            parsed = json.loads(json_str)
                            items = parsed if isinstance(parsed, list) else [parsed]
                            for item in items:
                                if isinstance(item, dict) and (item.get("name") or item.get("tool")):
                                    n = str(item.get("name") or item.get("tool")).lower().replace("_api", "")
                                    args = item.get("arguments") or item.get("input") or item
                                    temp_tool_calls.append({"id": f"cj_{uuid.uuid4().hex[:6]}", "name": NAME_MAP.get(n, n), "input": args})
                            continue
                    except: pass

                # 2. Parsing Naked JSON Lines (Common in DeepSeek R1)
                if not temp_tool_calls:
                    for line in full_raw_txt.split('\n'):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                item = json.loads(line)
                                potential_tools = {
                                    "file_path": "read_file",
                                    "command": "execute_shell",
                                    "expression": "calculator",
                                    "code": "run_python",
                                    "query": "tavily_search",
                                    "tool": "run_asymptote",
                                    "sources": "run_macro_analyzer"
                                }
                                for key, tool_name in potential_tools.items():
                                    if key in item:
                                        temp_tool_calls.append({"id": f"cn_{uuid.uuid4().hex[:6]}", "name": tool_name, "input": item})
                                        break
                            except: pass

                clean_display = full_raw_txt
                clean_display = re.sub(r'<tool_call>.*?(?=<tool_call>|</tool_call>|$)', '', clean_display, flags=re.DOTALL | re.IGNORECASE)
                clean_display = re.sub(r'</tool_call>', '', clean_display, flags=re.IGNORECASE)
                if temp_tool_calls:
                    lines = clean_display.split('\n')
                    clean_lines = [l for l in lines if not (l.strip().startswith('{') and l.strip().endswith('}'))]
                    clean_display = '\n'.join(clean_lines).strip()

                if clean_display.strip():
                    a_blocks.append({"text": clean_display.strip()})

                for tc in temp_tool_calls:
                    if not any(b.get("toolUse", {}).get("name") == tc["name"] for b in a_blocks):
                        a_blocks.append({"toolUse": {"toolUseId": tc["id"], "name": tc["name"], "input": tc["input"]}})

                if not a_blocks:
                    if txt: a_blocks.append({"text": txt})
                    else: break

                msgs.append({"role": "assistant", "content": a_blocks})
                
                has_tools = any("toolUse" in b for b in a_blocks)
                if has_tools:
                    tr = []
                    tasks = []
                    for b in a_blocks:
                        if "toolUse" in b:
                            tu = b["toolUse"]
                            yield self.sse({"type": "tool_exec", "name": tu["name"], "input": tu["input"]})
                            tasks.append((tu, tu["name"], exec_tool(tu["name"], tu["input"])))

                    results = await asyncio.gather(*(t[2] for t in tasks), return_exceptions=True)
                    for (tu, tool_name, _), res in zip(tasks, results):
                        if isinstance(res, Exception): res = {"error": str(res)}
                        yield self.sse({"type": "tool_result", "name": tool_name, "result": res})
                        tr.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"text": json.dumps(res)}],}})
                    msgs.append({"role": "user", "content": tr})
                else:
                    break

            except Exception as e:
                err_msg = f"Provider Connection Error: {str(e)}"
                msgs.append({"role": "assistant", "content": [{"text": f"⚠️ {err_msg}"}]})
                yield self.sse({"type": "error", "message": err_msg})
                return
        
        yield self.sse({
            "type": "usage",
            "input_tokens": t_in,
            "output_tokens": t_out
        })
