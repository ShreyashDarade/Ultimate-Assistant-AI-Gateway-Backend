import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

# Provider base URLs
PROVIDER_URLS: dict[str, str] = {
    "openai": "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "google": "https://generativelanguage.googleapis.com",
    "xai": "https://api.x.ai",
    "mistral": "https://api.mistral.ai",
    "cohere": "https://api.cohere.com",
    "groq": "https://api.groq.com/openai",
    "deepseek": "https://api.deepseek.com",
    "elevenlabs": "https://api.elevenlabs.io",
    "replicate": "https://api.replicate.com",
    "stability": "https://api.stability.ai",
    "fal": "https://fal.run",
}


class ClientPool:
    """Manages a shared httpx.AsyncClient per provider with connection pooling + HTTP/2."""

    def __init__(self):
        self._clients: dict[str, httpx.AsyncClient] = {}

    async def startup(self) -> None:
        for name, base_url in PROVIDER_URLS.items():
            self._clients[name] = httpx.AsyncClient(
                base_url=base_url,
                http2=True,
                timeout=httpx.Timeout(connect=5.0, read=120.0, write=30.0, pool=10.0),
                limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            )
            logger.info("client_created", provider=name)

    async def shutdown(self) -> None:
        for name, client in self._clients.items():
            await client.aclose()
            logger.info("client_closed", provider=name)
        self._clients.clear()

    def get(self, provider: str) -> httpx.AsyncClient:
        if provider not in self._clients:
            raise ValueError(f"No client for provider: {provider}")
        return self._clients[provider]
