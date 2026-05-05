from providers.bedrock import BedrockProvider
from providers.openai_compat import OpenAICompatProvider

def get_provider(mcfg: dict):
    api_type = mcfg.get("api_type")
    if api_type == "openai":
        return OpenAICompatProvider()
    else:
        return BedrockProvider()
