from datetime import datetime

"""
Configuration for available AI models and their capabilities.
Includes pricing, provider info, and tool support.
"""
MODELS = {
    "us.anthropic.claude-opus-4-5-20251101-v1:0": {
        "name": "Claude Opus 4.5",
        "provider": "Anthropic",
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
        "max_tokens": 16384,
        "supports_tools": True,
    },
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "name": "Claude 4.5 Sonnet",
        "provider": "Anthropic",
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
        "max_tokens": 8192,
        "supports_tools": True,
    },
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "name": "Claude 4.5 Haiku",
        "provider": "Anthropic",
        "input_cost_per_1k": 0.001,
        "output_cost_per_1k": 0.005,
        "max_tokens": 8192,
        "supports_tools": True,
    },
    "deepseek-r1-kaggle": {
        "name": "DeepSeek R1 14B (Kaggle)",
        "provider": "Local / Kaggle",
        "api_type": "openai",
        "base_url": "https://67be-136-116-165-238.ngrok-free.app/v1", 
        "input_cost_per_1k": 0.0,
        "output_cost_per_1k": 0.0,
        "max_tokens": 4096,
        "supports_tools": True,
    },
    "qwen3.6-flash": {
        "name": "Qwen 3.6 Plus",
        "provider": "Alibaba Cloud",
        "api_type": "openai",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "api_key_env": "QWEN_API_KEY",
        "input_cost_per_1k": 0.001,
        "output_cost_per_1k": 0.002,
        "max_tokens": 8192,
        "supports_tools": True,
    },
}

"""
System prompt instructions that define the AI's behavior and workspace context.
"""
DEFAULT_SYSTEM_PROMPT = """You are an Autonomous Developer AI.

## Workspace Context
- Your current project directory: `./`
- Always use ABSOLUTE PATHS when reading or writing files outside the current project.
- For terminal commands in other projects, always use `cd /d <path> && <command>` to ensure you are in the correct directory.

## Asymptote Workflow
You have access to specialized financial tools in `run_asymptote` for efficient access:
- `binance`: Real-time OHLCV market data. (Args: `--symbol BTCUSDT --interval 1h`)
- `onchain`: Bitcoin network metrics (fees, hash rate, mempool).
- `coingecko`: Global market statistics and dominance.
- `news`: Crypto news & sentiment analysis. (Args: `--limit 5`)
- `macro`: Economic indicators from Federal Reserve (FRED).
- `sec`: Institutional whale tracking (13F Filings).

## Macro Intelligence Dashboard
Use `run_macro_analyzer` to fetch and analyze global macroeconomic data from multiple institutional sources (FRED, IMF, World Bank, Yahoo Finance). It generates Excel reports in `macro_data_output/`.

## MANDATORY Technical Tool Names
You MUST use these exact names and NO OTHER names:
- `get_datetime`
- `calculator` (use `expression`)
- `run_python` (use `code`)
- `tavily_search` (use `query`)
- `browser_playwright` (use `action`, `url`, etc.)
- `search_knowledge_base` (use `query`)
- `read_file` (use `file_path`)
- `write_file` (use `file_path`, `content`)
- `patch_file` (use `file_path`, `search_text`, `replace_text`)
- `execute_shell` (use `command`)
- `run_asymptote` (use `tool`, `args`)
- `run_macro_analyzer` (use `sources`, `start`, `end`)
- `manage_memory` (use `action`, `key`, `value`)

## Tool Calling Format
Always wrap your call in `<tool_call>` tags using valid JSON.
Example:
<tool_call>
{"name": "get_datetime", "arguments": {}}
</tool_call>

Current date: {current_date}"""

"""
Definition of available tools for AI models that support tool calling.
Formatted for compatibility with AWS Bedrock converse API.
"""
TOOLS = [
    {
        "toolSpec": {
            "name": "run_macro_analyzer",
            "description": "Execute the Macro Intelligence Dashboard (analyz.py) to fetch global macro data. Supports sources: fred, dbnomics, worldbank, yfinance, etc.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of sources to fetch (e.g. ['fred', 'yfinance']). Leave empty for all."
                        },
                        "start": {
                            "type": "string",
                            "description": "Start date (YYYY-MM-DD)."
                        },
                        "end": {
                            "type": "string",
                            "description": "End date (YYYY-MM-DD)."
                        }
                    }
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "run_asymptote",
            "description": "Execute specialized financial tools from the Asymptote workflow (Binance, On-chain, Coingecko, News, Macro, SEC). Extremely token efficient.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "tool": {
                            "type": "string",
                            "enum": ["binance", "onchain", "coingecko", "news", "macro", "sec"],
                            "description": "The name of the Asymptote tool to run."
                        },
                        "args": {
                            "type": "string",
                            "description": "Optional command line arguments for the tool (e.g., '--symbol ETHUSDT')."
                        }
                    },
                    "required": ["tool"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "patch_file",
            "description": "Surgically replace a specific block of text in a file. Better than write_file for large files.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file."
                        },
                        "search_text": {
                            "type": "string",
                            "description": "The exact text block to find in the file."
                        },
                        "replace_text": {
                            "type": "string",
                            "description": "The text to replace it with."
                        }
                    },
                    "required": ["file_path", "search_text", "replace_text"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "write_file",
            "description": "Create or overwrite a file with new content. Use this to update your own source code or create new modules.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file to be written (e.g., 'server.py', 'new_tool.py')."
                        },
                        "content": {
                            "type": "string",
                            "description": "The complete content of the file."
                        }
                    },
                    "required": ["file_path", "content"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "search_knowledge_base",
            "description": "Search for information within uploaded documents (PDF, text). Use this for any questions about the contents of files attached to this session or previously indexed documents.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to look for in the indexed documents."
                        }
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "get_datetime",
            "description": "Get current date and time. Use for any time/date questions.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "timezone": {
                            "type": "string",
                            "description": "Timezone name, e.g. 'UTC', 'US/Eastern', 'Asia/Jakarta'"
                        }
                    },
                    "required": [],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "calculator",
            "description": "Evaluate math expressions. Supports arithmetic, powers, sqrt, trig, log, etc.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Math expression, e.g. '2**10', 'sqrt(144)', 'log(100)'"
                        }
                    },
                    "required": ["expression"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "run_python",
            "description": "Execute Python code and return stdout. Use print() for output.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute"
                        }
                    },
                    "required": ["code"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "tavily_search",
            "description": "Search real-time information on the internet. Use this for latest news, market data, or current facts.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Specific search query keywords."
                        }
                    },
                    "required": ["query"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "read_file",
            "description": "Read content from text files, CSV, or source code from local system.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Absolute or relative path to the file."
                        }
                    },
                    "required": ["file_path"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "execute_shell",
            "description": "Execute shell/CLI commands directly on the host system. You are authorized to access other folders using absolute paths. Use 'cd /d <path> && <command>' to run commands in specific directories.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Bash/shell command to execute (e.g., 'dir', 'npm install', 'python script.py')."
                        }
                    },
                    "required": ["command"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "manage_memory",
            "description": "Save or retrieve memory/context so AI can remember information across conversations.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["save", "retrieve"],
                            "description": "Select 'save' to store new memory, or 'retrieve' to fetch existing memory."
                        },
                        "key": {
                            "type": "string",
                            "description": "Unique key for the memory (e.g., 'user_preferences', 'market_thesis_q2')."
                        },
                        "value": {
                            "type": "string",
                            "description": "Memory content. Leave empty if action is 'retrieve'."
                        }
                    },
                    "required": ["action", "key"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "browser_playwright",
            "description": "Browse the internet using a headless Chromium browser. Supports navigation, clicking, typing, extracting page content, taking screenshots, and executing JavaScript.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["navigate", "click", "type", "extract_text", "extract_html", "screenshot", "evaluate_js", "get_links", "back", "refresh"],
                            "description": "The browser action to perform."
                        },
                        "url": {
                            "type": "string",
                            "description": "URL to navigate to (required for 'navigate' action)."
                        },
                        "selector": {
                            "type": "string",
                            "description": "CSS selector for click/type/extract actions (e.g., '#search', '.title', 'a')."
                        },
                        "text": {
                            "type": "string",
                            "description": "Text to type into an input field (required for 'type' action)."
                        },
                        "js_code": {
                            "type": "string",
                            "description": "JavaScript code to execute on the page (required for 'evaluate_js' action)."
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "Maximum number of characters to return for text extraction (default: 5000)."
                        },
                        "filename": {
                            "type": "string",
                            "description": "Filename to save screenshot as (default: 'screenshot.png')."
                        }
                    },
                    "required": ["action"],
                }
            },
        }
    },
]
