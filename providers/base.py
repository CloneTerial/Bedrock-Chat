from abc import ABC, abstractmethod
from typing import AsyncGenerator

class BaseProvider(ABC):
    @abstractmethod
    async def stream_chat(self, req, conv, sys_prompt, mcfg, use_tools) -> AsyncGenerator[str, None]:
        pass
