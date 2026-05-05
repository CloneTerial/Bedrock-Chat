import os
import aiofiles

async def read_file(inp: dict):
    """Read content from a local text file with a 100k character limit."""
    file_path = inp.get("file_path", "")
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(100000)
        return {"file_path": file_path, "content": content}
    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}

async def write_file(inp: dict):
    file_path = inp.get("file_path", "")
    content = inp.get("content", "")

    if not file_path:
        return {"error": "file_path is required"}

    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        tmp_path = file_path + ".tmp"

        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            for i in range(0, len(content), 8192):
                await f.write(content[i:i+8192])

        os.replace(tmp_path, file_path)

        msg = "File updated successfully."

        if os.path.basename(file_path) in ["server.py", "config.py"]:
            msg += " WARNING: Server will restart shortly due to changes in core files."

        return {
            "status": "success",
            "file_path": file_path,
            "message": msg
        }

    except Exception as e:
        return {"error": f"Failed to write file: {str(e)}"}

async def patch_file(inp: dict):
    """Surgically replace a specific text block in a file."""
    file_path = inp.get("file_path", "")
    search_text = inp.get("search_text", "")
    replace_text = inp.get("replace_text", "")
    try:
        if not os.path.exists(file_path):
            return {"error": f"File not found: {file_path}"}
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if search_text not in content:
            return {"error": "Search text not found in file."}
        
        if content.count(search_text) > 1:
            return {"error": "Search text found multiple times. Please be more specific."}
        
        new_content = content.replace(search_text, replace_text)
        
        msg = f"File {file_path} patched successfully."
        if file_path in ["server.py", "config.py"]:
            msg += " WARNING: Server will restart shortly due to changes in core files."

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return {"status": "success", "message": msg}
    except Exception as e:
        return {"error": f"Failed to patch file: {str(e)}"}
