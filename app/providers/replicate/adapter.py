"""Replicate adapter — open models: image gen (Flux, SD), video gen."""

import asyncio

from app.providers.base import BaseProvider, ImageGenCapable, VideoGenCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import MediaResult, ModelInfo, UnifiedRequest


class ReplicateAdapter(BaseProvider, ImageGenCapable, VideoGenCapable):
    name = "replicate"
    base_url = "https://api.replicate.com"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.IMAGE): ["black-forest-labs/flux-1.1-pro", "black-forest-labs/flux-schnell", "stability-ai/sdxl"],
            (Modality.TEXT, Modality.VIDEO): ["minimax/video-01-live"],
            (Modality.IMAGE, Modality.VIDEO): ["minimax/video-01-live"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="black-forest-labs/flux-1.1-pro", name="Flux 1.1 Pro", provider="replicate", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="black-forest-labs/flux-schnell", name="Flux Schnell", provider="replicate", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="stability-ai/sdxl", name="SDXL", provider="replicate", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="minimax/video-01-live", name="MiniMax Video-01", provider="replicate", modalities=["text→video", "image→video"], context_window=None, max_output_tokens=None),
        ]

    async def _run_prediction(self, model: str, input_data: dict, api_key: str) -> dict:
        """Create a prediction and poll until complete."""
        payload = {"version": model, "input": input_data}

        # If model contains '/', use the models endpoint
        if "/" in model:
            resp = await self.client.post(
                f"/v1/models/{model}/predictions",
                json={"input": input_data},
                headers=self._headers(api_key),
            )
        else:
            resp = await self.client.post(
                "/v1/predictions",
                json=payload,
                headers=self._headers(api_key),
            )
        resp.raise_for_status()
        prediction = resp.json()

        # Poll for completion
        poll_url = prediction.get("urls", {}).get("get", f"/v1/predictions/{prediction['id']}")
        for _ in range(120):  # max 2 min polling
            await asyncio.sleep(1)
            poll_resp = await self.client.get(poll_url, headers=self._headers(api_key))
            poll_resp.raise_for_status()
            result = poll_resp.json()
            if result["status"] in ("succeeded", "failed", "canceled"):
                return result
        return prediction

    @with_retry()
    async def text_to_image(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "black-forest-labs/flux-schnell"
        input_data = {
            "prompt": req.prompt,
            "num_outputs": 1,
        }
        if req.options:
            input_data.update({k: v for k, v in req.options.items() if k in ("width", "height", "num_inference_steps", "guidance_scale")})

        result = await self._run_prediction(model, input_data, api_key)
        output = result.get("output", [])
        file_url = output[0] if isinstance(output, list) and output else str(output)
        return MediaResult(file_url=file_url, mime_type="image/png", model=model, provider="replicate")

    @with_retry()
    async def text_to_video(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "minimax/video-01-live"
        input_data = {"prompt": req.prompt}
        if req.options:
            input_data.update(req.options)

        result = await self._run_prediction(model, input_data, api_key)
        output = result.get("output", "")
        file_url = output[0] if isinstance(output, list) and output else str(output)
        return MediaResult(file_url=file_url, mime_type="video/mp4", model=model, provider="replicate")

    @with_retry()
    async def image_to_video(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "minimax/video-01-live"
        input_data = {"image": req.input_url, "prompt": req.prompt or ""}
        if req.options:
            input_data.update(req.options)

        result = await self._run_prediction(model, input_data, api_key)
        output = result.get("output", "")
        file_url = output[0] if isinstance(output, list) and output else str(output)
        return MediaResult(file_url=file_url, mime_type="video/mp4", model=model, provider="replicate")
