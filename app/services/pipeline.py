"""Multi-step pipeline — composes conversions when no single provider covers the route.

Example: audio → [STT] → text → [translate via chat] → text → [TTS] → audio
Each hop reuses the modality router.
"""

import uuid

from app.core.logging import get_logger
from app.schemas.provider import MediaResult, UnifiedRequest, UnifiedResponse
from app.services.router import ModalityRouter

logger = get_logger(__name__)

# Known multi-step routes: (input, output) → [intermediate steps]
PIPELINE_ROUTES: dict[tuple[str, str], list[tuple[str, str]]] = {
    ("audio", "audio"): [("audio", "text"), ("text", "text"), ("text", "audio")],  # STT → Chat → TTS
    ("image", "audio"): [("image", "text"), ("text", "audio")],  # Vision → TTS
    ("audio", "image"): [("audio", "text"), ("text", "image")],  # STT → ImageGen
    ("image", "image"): [("image", "text"), ("text", "image")],  # Vision → ImageGen
    ("video", "text"): [("video", "text")],  # direct if available
}


class Pipeline:
    def __init__(self, router: ModalityRouter):
        self.router = router

    async def execute(
        self,
        user_id: uuid.UUID,
        input_data: str,
        input_modality: str,
        output_modality: str,
        preferred_provider: str | None = None,
        options: dict | None = None,
    ) -> UnifiedResponse | MediaResult:
        # Check if direct route exists
        capable = self.router.registry.get_capable_providers(input_modality, output_modality)
        if capable:
            req = UnifiedRequest(prompt=input_data, options=options)
            return await self.router.route(
                req, user_id, input_modality, output_modality, preferred_provider
            )

        # Otherwise, use pipeline
        route_key = (input_modality, output_modality)
        steps = PIPELINE_ROUTES.get(route_key)
        if not steps:
            from app.core.exceptions import CapabilityNotSupported
            raise CapabilityNotSupported(input_modality, output_modality)

        logger.info("pipeline_start", steps=len(steps), route=f"{input_modality}→{output_modality}")
        current_data = input_data
        result = None

        for i, (in_mod, out_mod) in enumerate(steps):
            req = UnifiedRequest(prompt=current_data, options=options)
            result = await self.router.route(req, user_id, in_mod, out_mod, preferred_provider)

            # Extract text from result for next step
            if isinstance(result, UnifiedResponse) and result.content:
                current_data = result.content
            elif isinstance(result, MediaResult) and result.file_url:
                current_data = result.file_url

            logger.info("pipeline_step", step=i + 1, conversion=f"{in_mod}→{out_mod}")

        return result
