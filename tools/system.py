import asyncio
import os
import json
import math
import io
from datetime import datetime
from contextlib import redirect_stdout, redirect_stderr

async def execute_shell(inp: dict):
    """Execute a shell command in a separate thread for async compatibility."""
    command = inp.get("command", "")
    
    def sync_run():
        import subprocess
        return subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=False
        )

    try:
        result = await asyncio.to_thread(sync_run)
        
        return {
            "command": command,
            "stdout": result.stdout.decode(errors="replace")[:5000],
            "stderr": result.stderr.decode(errors="replace")[:5000],
            "returncode": result.returncode
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        err_msg = str(e) if str(e) else repr(e)
        return {"error": f"Failed to execute shell (Threaded): {err_msg}", "detail": error_detail}

async def run_python(inp: dict):
    """Execute Python code and capture stdout/stderr."""
    code = inp.get("code", "")
    so, se = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(so), redirect_stderr(se):
            exec(code, {
                "__builtins__": __builtins__,
                "math": math,
                "json": json,
                "datetime": __import__("datetime"),
            })
        return {
            "stdout": so.getvalue() or "(no output)",
            "stderr": se.getvalue() or None,
        }
    except Exception as e:
        return {"stdout": so.getvalue(), "error": str(e)}

async def manage_memory(inp: dict):
    """Save or retrieve context data from a local JSON file."""
    action = inp.get("action")
    key = inp.get("key")
    value = inp.get("value", "")
    memory_file = "memory.json"
    
    mem_data = {}
    if os.path.exists(memory_file):
        with open(memory_file, "r") as f:
            try:
                mem_data = json.load(f)
            except json.JSONDecodeError:
                pass
                
    if action == "save":
        mem_data[key] = value
        with open(memory_file, "w") as f:
            json.dump(mem_data, f, indent=2)
        return {"status": "success", "message": f"Memory '{key}' saved successfully."}
        
    elif action == "retrieve":
        if key in mem_data:
            return {"key": key, "value": mem_data[key]}
        else:
            keys = [k for k in mem_data.keys() if key.lower() in k.lower()]
            if keys:
                return {"warning": f"Exact key not found. Found similar keys: {keys}"}
            return {"error": f"Memory '{key}' not found."}

async def get_datetime(inp: dict):
    """Get current date and time in specified timezone."""
    tz_str = inp.get("timezone", "UTC")
    try:
        import zoneinfo
        now = datetime.now(zoneinfo.ZoneInfo(tz_str))
    except Exception:
        now = datetime.utcnow()
        tz_str = "UTC"
    return {
        "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": tz_str,
        "day_of_week": now.strftime("%A"),
    }

async def calculator(inp: dict):
    """Evaluate math expressions safely using a restricted namespace."""
    expr = inp.get("expression", "")
    ns = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
    ns.update(abs=abs, round=round, min=min, max=max, pow=pow)
    try:
        result = eval(expr, {"__builtins__": {}}, ns)
        return {"expression": expr, "result": str(result)}
    except Exception as e:
        return {"error": f"Math error: {str(e)}"}
