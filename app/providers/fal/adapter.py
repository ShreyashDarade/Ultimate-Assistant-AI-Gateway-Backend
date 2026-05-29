"""Fal adapter — fast media generation (image + video)."""

import asyncio

from app.providers.base import BaseProvider, ImageGenCapable, VideoGenCapable
from app.providers.capabilities import Modality, ModalityPair
from app.providers.retry import with_retry
from app.schemas.provider import MediaResult, ModelInfo, UnifiedRequest


class FalAdapter(BaseProvider, ImageGenCapable, VideoGenCapable):
    name = "fal"
    base_url = "https://fal.run"

    def _headers(self, api_key: str) -> dict:
        return {"Authorization": f"Key {api_key}", "Content-Type": "application/json"}

    def get_capabilities(self) -> dict[ModalityPair, list[str]]:
        return {
            (Modality.TEXT, Modality.IMAGE): ["fal-ai/flux/dev", "fal-ai/flux-realism", "fal-ai/recraft-v3"],
            (Modality.TEXT, Modality.VIDEO): ["fal-ai/kling-video/v2/master/text-to-video"],
            (Modality.IMAGE, Modality.VIDEO): ["fal-ai/kling-video/v2/master/image-to-video"],
        }

    def get_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(id="fal-ai/flux/dev", name="Flux Dev", provider="fal", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="fal-ai/flux-realism", name="Flux Realism", provider="fal", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="fal-ai/recraft-v3", name="Recraft V3", provider="fal", modalities=["text→image"], context_window=None, max_output_tokens=None),
            ModelInfo(id="fal-ai/kling-video/v2/master/text-to-video", name="Kling Video V2 (txt2vid)", provider="fal", modalities=["text→video"], context_window=None, max_output_tokens=None),
            ModelInfo(id="fal-ai/kling-video/v2/master/image-to-video", name="Kling Video V2 (img2vid)", provider="fal", modalities=["image→video"], context_window=None, max_output_tokens=None),
        ]

    async def _submit_and_poll(self, model: str, input_data: dict, api_key: str) -> dict:
        # Submit to queue
        resp = await self.client.post(
            f"/{model}",
            json=input_data,
            headers=self._headers(api_key),
        )
        resp.raise_for_status()
        result = resp.json()

        # If result is immediate (synchronous mode)
        if "images" in result or "video" in result:
            return result

        # Queue mode — poll for result
        request_id = result.get("request_id")
        if not request_id:
            return result

        status_url = f"https://queue.fal.run/{model}/requests/{request_id}/status"
        for _ in range(180):  # max 3 min polling
            await asyncio.sleep(1)
            status_resp = await self.client.get(status_url, headers=self._headers(api_key))
            status_resp.raise_for_status()
            status_data = status_resp.json()
            if status_data.get("status") == "COMPLETED":
                result_url = f"https://queue.fal.run/{model}/requests/{request_id}"
                result_resp = await self.client.get(result_url, headers=self._headers(api_key))
                result_resp.raise_for_status()
                return result_resp.json()
            elif status_data.get("status") in ("FAILED",):
                raise RuntimeError(f"Fal job failed: {status_data}")
        raise TimeoutError(f"Fal job timed out for model {model}")

    @with_retry()
    async def text_to_image(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "fal-ai/flux/dev"
        input_data = {"prompt": req.prompt, "num_images": 1}
        if req.options:
            input_data.update({k: v for k, v in req.options.items() if k in ("image_size", "num_inference_steps", "guidance_scale")})

        result = await self._submit_and_poll(model, input_data, api_key)
        images = result.get("images", [])
        file_url = images[0].get("url", "") if images else ""
        return MediaResult(file_url=file_url, mime_type="image/png", model=model, provider="fal")

    @with_retry()
    async def text_to_video(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "fal-ai/kling-video/v2/master/text-to-video"
        input_data = {"prompt": req.prompt}
        if req.options:
            input_data.update(req.options)

        result = await self._submit_and_poll(model, input_data, api_key)
        video = result.get("video", {})
        file_url = video.get("url", "") if isinstance(video, dict) else str(video)
        return MediaResult(file_url=file_url, mime_type="video/mp4", model=model, provider="fal")

    @with_retry()
    async def image_to_video(self, req: UnifiedRequest, api_key: str) -> MediaResult:
        model = req.model or "fal-ai/kling-video/v2/master/image-to-video"
        input_data = {"image_url": req.input_url, "prompt": req.prompt or ""}
        if req.options:
            input_data.update(req.options)

        result = await self._submit_and_poll(model, input_data, api_key)
        video = result.get("video", {})
        file_url = video.get("url", "") if isinstance(video, dict) else str(video)
        return MediaResult(file_url=file_url, mime_type="video/mp4", model=model, provider="fal")
