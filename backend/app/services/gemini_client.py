"""Gemini SDK access shared by generation, vision and OCR."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from google import genai
from google.genai import types

from app.core.config import settings

# Hang protection: overloaded Gemini sometimes never returns instead of 503.
_SYNC_TIMEOUT_S = 90


def gemini_model_name() -> str:
    # Preserve existing Gemini-only installations using LLM_MODEL.
    name = settings.LLM_MODEL.strip()
    return name if name.startswith("gemini-") else settings.GEMINI_MODEL


def image_part(data: bytes, mime_type: str):
    return types.Part.from_bytes(data=data, mime_type=mime_type)


async def generate_gemini_content(contents, config=None):
    async with genai.Client(api_key=settings.GEMINI_API_KEY).aio as client:
        return await client.models.generate_content(
            model=gemini_model_name(), contents=contents, config=config,
        )


def generate_gemini_content_sync(contents, timeout_s: float = _SYNC_TIMEOUT_S):
    def _call():
        with genai.Client(api_key=settings.GEMINI_API_KEY) as client:
            return client.models.generate_content(
                model=gemini_model_name(), contents=contents,
            )

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(_call)
        try:
            return fut.result(timeout=timeout_s)
        except FuturesTimeout as e:
            raise TimeoutError(f"Gemini sync call exceeded {timeout_s}s") from e
