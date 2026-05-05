from tools.browser import browser_playwright
from tools.files import read_file, write_file, patch_file
from tools.system import execute_shell, run_python, manage_memory, get_datetime, calculator
from tools.asymptote import run_asymptote, tavily_search, search_knowledge_base
from tools.macro_analyzer import run_macro_analyzer

TOOL_MAP = {
    "browser_playwright": browser_playwright,
    "read_file": read_file,
    "write_file": write_file,
    "patch_file": patch_file,
    "execute_shell": execute_shell,
    "run_python": run_python,
    "manage_memory": manage_memory,
    "get_datetime": get_datetime,
    "calculator": calculator,
    "run_asymptote": run_asymptote,
    "tavily_search": tavily_search,
    "search_knowledge_base": search_knowledge_base,
    "run_macro_analyzer": run_macro_analyzer
}

async def exec_tool(name: str, inp: dict) -> dict:
    """Execute a tool by name with provided input arguments."""
    func = TOOL_MAP.get(name)
    if not func:
        return {"error": f"Tool '{name}' not found in registry."}
    
    try:
        return await func(inp)
    except Exception as e:
        return {"error": f"Error executing tool '{name}': {str(e)}"}
