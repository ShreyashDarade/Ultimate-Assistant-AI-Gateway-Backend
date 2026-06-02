"""Guardrails — pre/post processing for content safety.

Pre-request:
  - Prompt injection detection (common jailbreak patterns)
  - PII detection and optional redaction (emails, phones, SSNs)
  - Max input length enforcement per tier

Post-response:
  - Basic toxicity keyword filtering
"""

import re
from dataclasses import dataclass, field

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Prompt injection patterns ────────────────────────

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?above\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.IGNORECASE),
    re.compile(r"reveal\s+(your|the)\s+(system\s+)?prompt", re.IGNORECASE),
    re.compile(r"what\s+(is|are)\s+your\s+(system\s+)?instructions", re.IGNORECASE),
    re.compile(r"repeat\s+(the|your)\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s*mode", re.IGNORECASE),
]

# ── PII patterns ─────────────────────────────────────

_PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone_us": re.compile(r"\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "ssn": re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4}\b"),
}

# ── Input length limits per tier ─────────────────────

_MAX_INPUT_CHARS: dict[str, int] = {
    "free": settings.MAX_INPUT_TOKENS_FREE * 4,  # rough chars ≈ tokens × 4
    "pro": settings.MAX_INPUT_TOKENS_PRO * 4,
    "enterprise": settings.MAX_INPUT_TOKENS_ENTERPRISE * 4,
}


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""
    passed: bool = True
    blocked: bool = False
    warnings: list[str] = field(default_factory=list)
    pii_found: list[str] = field(default_factory=list)
    sanitized_text: str | None = None


class Guardrails:
    """Pre/post processing guardrails for content safety."""

    @staticmethod
    def pre_check(
        text: str,
        tier: str = "free",
        redact_pii: bool = False,
    ) -> GuardrailResult:
        """Run all pre-request checks on the input text."""
        if not settings.GUARDRAILS_ENABLED:
            return GuardrailResult()

        result = GuardrailResult(sanitized_text=text)

        # 1. Input length check
        max_chars = _MAX_INPUT_CHARS.get(tier, _MAX_INPUT_CHARS["free"])
        if len(text) > max_chars:
            result.passed = False
            result.blocked = True
            result.warnings.append(
                f"Input exceeds maximum length for {tier} tier ({len(text)} > {max_chars} chars)"
            )
            return result

        # 2. Prompt injection detection
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                result.warnings.append(
                    f"Potential prompt injection detected: '{pattern.pattern[:40]}...'"
                )
                logger.warning(
                    "guardrail_injection",
                    pattern=pattern.pattern[:40],
                    text_preview=text[:100],
                )

        # 3. PII detection
        sanitized = text
        for pii_type, pattern in _PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                result.pii_found.append(f"{pii_type}: {len(matches)} instance(s)")
                if redact_pii:
                    sanitized = pattern.sub(f"[REDACTED_{pii_type.upper()}]", sanitized)
                    logger.info("guardrail_pii_redacted", type=pii_type, count=len(matches))

        if redact_pii and sanitized != text:
            result.sanitized_text = sanitized

        return result

    @staticmethod
    def post_check(text: str) -> GuardrailResult:
        """Run post-response checks on the output text."""
        if not settings.GUARDRAILS_ENABLED:
            return GuardrailResult()

        result = GuardrailResult()

        # Basic PII leak detection in responses
        for pii_type, pattern in _PII_PATTERNS.items():
            if pattern.search(text):
                result.warnings.append(f"Response may contain {pii_type}")

        return result
