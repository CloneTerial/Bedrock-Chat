import json
import asyncio
import os
import boto3
from datetime import datetime
from typing import AsyncGenerator
from providers.base import BaseProvider
from tools import exec_tool

class BedrockProvider(BaseProvider):
    """
    Provider implementation for AWS Bedrock models.
    Supports streaming and tool calling via the converse_stream API.
    """
    def __init__(self):
        self.bedrock = boto3.client(
            "bedrock-runtime",
            region_name=os.getenv("AWS_REGION", "us-east-1"),
        )

    def sse(self, data: dict) -> str:
        """Format dictionary as Server-Sent Events (SSE) string."""
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def stream_chat(self, req, conv, sys_prompt, mcfg, use_tools) -> AsyncGenerator[str, None]:
        """Stream chat completions from Bedrock, handling tool usage and metadata."""
        from config import TOOLS
        msgs = conv["messages"]
        model_id = req.model or mcfg.get("model_id")
        temp = req.temperature if req.temperature is not None else 0.7
        max_tok = req.max_tokens or 4096
        
        t_in = 0
        t_out = 0

        for _ in range(50):
            kwargs = dict(
                modelId=model_id,
                messages=msgs,
                system=[{"text": sys_prompt}],
                inferenceConfig={"maxTokens": max_tok, "temperature": temp},
            )
            if use_tools:
                kwargs["toolConfig"] = {"tools": TOOLS}

            try:
                resp = self.bedrock.converse_stream(**kwargs)
            except Exception as e:
                err_msg = f"Bedrock API Error: {str(e)}"
                msgs.append({"role": "assistant", "content": [{"text": f"⚠️ {err_msg}"}]})
                yield self.sse({"type": "error", "message": err_msg})
                return

            a_blocks = []
            txt = ""
            cur_tool = None
            tool_json = ""
            stop = "end_turn"

            try:
                for ev in resp["stream"]:
                    if "contentBlockStart" in ev:
                        s = ev["contentBlockStart"].get("start", {})
                        if "toolUse" in s:
                            if txt: a_blocks.append({"text": txt}); txt = ""
                            cur_tool = {"id": s["toolUse"]["toolUseId"], "name": s["toolUse"]["name"]}
                            tool_json = ""
                            yield self.sse({"type": "tool_start", "name": cur_tool["name"]})

                    if "contentBlockDelta" in ev:
                        d = ev["contentBlockDelta"].get("delta", {})
                        if "text" in d:
                            txt += d["text"]
                            yield self.sse({"type": "text", "content": d["text"]})
                        if "toolUse" in d:
                            tool_json += d["toolUse"].get("input", "")

                    if "contentBlockStop" in ev:
                        if txt: a_blocks.append({"text": txt}); txt = ""
                        if cur_tool:
                            try: ti = json.loads(tool_json) if tool_json else {}
                            except Exception: ti = {}
                            a_blocks.append({"toolUse": {"toolUseId": cur_tool["id"], "name": cur_tool["name"], "input": ti}})
                            cur_tool = None
                    if "messageStop" in ev: stop = ev["messageStop"].get("stopReason", "end_turn")
                    if "metadata" in ev:
                        u = ev["metadata"].get("usage", {})
                        t_in += u.get("inputTokens", 0)
                        t_out += u.get("outputTokens", 0)

            except Exception as e:
                yield self.sse({"type": "error", "message": str(e)})
                break

            msgs.append({"role": "assistant", "content": a_blocks})

            if stop == "tool_use":
                tr = []
                tasks = []
                for b in a_blocks:
                    if "toolUse" not in b: continue
                    tu = b["toolUse"]
                    tool_name = tu["name"]
                    tool_input = tu.get("input", {})
                    yield self.sse({"type": "tool_exec", "name": tool_name, "input": tool_input})
                    tasks.append((tu, tool_name, exec_tool(tool_name, tool_input)))

                results = await asyncio.gather(*(t[2] for t in tasks), return_exceptions=True)
                for (tu, tool_name, _), res in zip(tasks, results):
                    if isinstance(res, Exception): res = {"error": f"Internal task error: {str(res)}"}
                    yield self.sse({"type": "tool_result", "name": tool_name, "result": res})
                    tr.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"text": json.dumps(res)}],}})
                msgs.append({"role": "user", "content": tr})
            else:
                break
        
        yield self.sse({
            "type": "usage",
            "input_tokens": t_in,
            "output_tokens": t_out
        })
