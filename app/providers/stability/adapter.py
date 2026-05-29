"""Stability AI adapter — image generation (Stable Diffusion, Stable Image)."""

from app.providers.base import BaseProvider, ImageGenCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import MediaResult, ModelInfo, UnifiedRequest


class StabilityAdapter(BaseProvider, ImageGenCapable):
    name = "stability"
    base_url = "https://api.stability.ai"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.IMAGE): ["sd3.5-large", "sd3.5-medium", "sd3-turbo"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="sd3.5-large", name="Stable Diffusion 3.5 Large", provider="stability", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="sd3.5-medium", name="Stable Diffusion 3.5 Medium", provider="stability", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="sd3-turbo", name="Stable Diffusion 3 Turbo", provider="stability", modalities=["text→image"], context_window=None, max_output_tokens=None),
        ]

    @with_retry()
    async def text_to_image(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "sd3.5-large"
        headers = {**self._headers(api_key), "Content-Type": "multipart/form-data"}

        form_data = {
            "prompt": req.prompt,
            "model": model,
            "output_format": "png",
        }
        if req.options:
            if "negative_prompt" in req.options:
                form_data["negative_prompt"] = req.options["negative_prompt"]
            if "aspect_ratio" in req.options:
                form_data["aspect_ratio"] = req.options["aspect_ratio"]

        resp = await self.client.post(
            "/v2beta/stable-image/generate/sd3",
            data=form_data,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        # Returns base64 image or URL depending on mode
        image_data = data.get("image", "")
        return MediaResult(
            file_url=image_data,  # base64 — caller should upload to S3
            mime_type="image/png",
            model=model,
            provider="stability",
        )
