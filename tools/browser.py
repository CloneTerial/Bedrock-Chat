import asyncio
import os
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import sync_playwright

class SyncBrowserManager:
    """Uses sync Playwright API running in a dedicated thread for Windows compatibility."""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)
    
    def _ensure_browser(self):
        """Initialize browser if not already running (called in thread)."""
        with self._lock:
            if not self.playwright:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(headless=True)
                self.context = self.browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                )
                self.page = self.context.new_page()
    
    def _run_action(self, action: str, **kwargs):
        """Execute browser action synchronously (called in thread)."""
        self._ensure_browser()
        page = self.page
        
        if action == "navigate":
            page.goto(kwargs["url"], wait_until="domcontentloaded", timeout=60000)
            return {"status": "success", "url": page.url, "title": page.title()}
        
        elif action == "click":
            page.click(kwargs["selector"], timeout=10000)
            return {"status": "success", "message": f"Clicked {kwargs['selector']}"}
        
        elif action == "type":
            page.fill(kwargs["selector"], kwargs["text"], timeout=10000)
            return {"status": "success", "message": f"Typed text into {kwargs['selector']}"}
        
        elif action == "extract_text":
            max_len = kwargs.get("max_length", 5000)
            text_content = page.evaluate("() => document.body.innerText")
            return {"status": "success", "content": text_content[:max_len]}
        
        elif action == "extract_html":
            max_len = kwargs.get("max_length", 5000)
            html = page.content()
            return {"status": "success", "html": html[:max_len]}
        
        elif action == "get_links":
            links = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.innerText.trim(),
                    href: a.href
                })).filter(l => l.href.startsWith('http'))
            }""")
            return {"status": "success", "links": links[:50]}
        
        elif action == "screenshot":
            filename = kwargs.get("filename", f"screenshot_{uuid.uuid4().hex[:8]}.png")
            # Ensure static directory exists relative to root if needed, 
            # but usually it's in the same folder as server.py
            path = os.path.join("static", filename)
            page.screenshot(path=path)
            return {"status": "success", "url": f"/static/{filename}"}
        
        elif action == "evaluate_js":
            res = page.evaluate(kwargs["js_code"])
            return {"status": "success", "result": res}
        
        elif action == "back":
            page.go_back()
            return {"status": "success", "url": page.url}
        
        elif action == "refresh":
            page.reload()
            return {"status": "success", "url": page.url}
        
        else:
            return {"error": f"Unknown browser action: {action}"}
    
    async def execute(self, action: str, **kwargs):
        """Async wrapper that runs sync playwright in thread pool."""
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                self._executor, 
                lambda: self._run_action(action, **kwargs)
            )
            return result
        except Exception as e:
            import traceback
            return {"error": f"Browser action '{action}' failed: {str(e)}", "traceback": traceback.format_exc()}
    
    def close_sync(self):
        """Close browser synchronously."""
        with self._lock:
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None

browser_mgr = SyncBrowserManager()

async def browser_playwright(inp: dict):
    action = inp.get("action")
    return await browser_mgr.execute(
        action,
        url=inp.get("url"),
        selector=inp.get("selector"),
        text=inp.get("text"),
        js_code=inp.get("js_code"),
        max_length=inp.get("max_length", 5000),
        filename=inp.get("filename")
    )
