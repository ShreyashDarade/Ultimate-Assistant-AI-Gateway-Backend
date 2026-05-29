"""Token counting per provider."""

import tiktoken


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens for OpenAI-compatible models using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Rough cost estimation. Prices in USD per 1M tokens."""
    PRICING = {
        ("openai", "gpt-4o"): (2.50, 10.00),
        ("openai", "gpt-4o-mini"): (0.15, 0.60),
        ("openai", "gpt-4.1"): (2.00, 8.00),
        ("openai", "gpt-4.1-mini"): (0.40, 1.60),
        ("openai", "gpt-4.1-nano"): (0.10, 0.40),
        ("anthropic", "claude-sonnet-4-20250514"): (3.00, 15.00),
        ("anthropic", "claude-opus-4-20250514"): (15.00, 75.00),
        ("anthropic", "claude-3-5-haiku-20241022"): (0.80, 4.00),
        ("google", "gemini-2.5-flash"): (0.15, 0.60),
        ("google", "gemini-2.5-pro"): (1.25, 10.00),
        ("groq", "llama-3.3-70b-versatile"): (0.59, 0.79),
        ("deepseek", "deepseek-chat"): (0.27, 1.10),
        ("mistral", "mistral-large-latest"): (2.00, 6.00),
        ("cohere", "command-r"): (0.15, 0.60),
        ("xai", "grok-3-fast"): (5.00, 25.00),
    }
    rates = PRICING.get((provider, model), (1.0, 3.0))
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1_000_000
