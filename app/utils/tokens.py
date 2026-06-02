"""Token counting per provider + pricing data."""

import tiktoken


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens for OpenAI-compatible models using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


# Prices in USD per 1M tokens: (input_price, output_price)
PRICING: dict[tuple[str, str], tuple[float, float]] = {
    # OpenAI
    ("openai", "gpt-4o"): (2.50, 10.00),
    ("openai", "gpt-4o-mini"): (0.15, 0.60),
    ("openai", "gpt-4.1"): (2.00, 8.00),
    ("openai", "gpt-4.1-mini"): (0.40, 1.60),
    ("openai", "gpt-4.1-nano"): (0.10, 0.40),
    ("openai", "o3"): (2.00, 8.00),
    ("openai", "o4-mini"): (1.10, 4.40),
    # Anthropic
    ("anthropic", "claude-sonnet-4-20250514"): (3.00, 15.00),
    ("anthropic", "claude-opus-4-20250514"): (15.00, 75.00),
    ("anthropic", "claude-3-5-haiku-20241022"): (0.80, 4.00),
    # Google
    ("google", "gemini-2.5-flash"): (0.15, 0.60),
    ("google", "gemini-2.5-pro"): (1.25, 10.00),
    # Groq
    ("groq", "llama-3.3-70b-versatile"): (0.59, 0.79),
    # DeepSeek
    ("deepseek", "deepseek-chat"): (0.27, 1.10),
    # Mistral
    ("mistral", "mistral-large-latest"): (2.00, 6.00),
    # Cohere
    ("cohere", "command-r"): (0.15, 0.60),
    ("cohere", "command-r-plus"): (2.50, 10.00),
    # xAI
    ("xai", "grok-3-fast"): (5.00, 25.00),
    # Ollama (local — effectively free)
    ("ollama", "llama3.2"): (0.0, 0.0),
    ("ollama", "llama3.2:1b"): (0.0, 0.0),
    ("ollama", "llama3.1"): (0.0, 0.0),
    ("ollama", "llama3.1:70b"): (0.0, 0.0),
    ("ollama", "mistral"): (0.0, 0.0),
    ("ollama", "mistral-nemo"): (0.0, 0.0),
    ("ollama", "phi4"): (0.0, 0.0),
    ("ollama", "gemma3"): (0.0, 0.0),
    ("ollama", "qwen3"): (0.0, 0.0),
    ("ollama", "deepseek-r1"): (0.0, 0.0),
    ("ollama", "codellama"): (0.0, 0.0),
    ("ollama", "command-r"): (0.0, 0.0),
}


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Rough cost estimation. Returns cost in USD."""
    rates = PRICING.get((provider, model), (1.0, 3.0))
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000
