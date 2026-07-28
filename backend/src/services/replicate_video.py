from __future__ import annotations

import asyncio
from typing import Any, Mapping

import httpx

REPLICATE_API_BASE_URL = "https://api.replicate.com/v1"


async def create_product_video_prediction(
    *,
    api_token: str,
    model: str,
    image_url: str,
    prompt: str,
    duration: int = 5,
    resolution: str = "720p",
    aspect_ratio: str = "9:16",
    image_field: str = "start_image",
    wait_seconds: int = 60,
) -> Mapping[str, Any]:
    if not api_token.strip():
        raise RuntimeError("REPLICATE_API_TOKEN is not configured")

    if not model.strip() or "/" not in model:
        raise RuntimeError("REPLICATE_VIDEO_MODEL must be in owner/model format")

    if not image_url.strip().startswith(("https://", "http://")):
        raise ValueError("image_url must be a public HTTPS URL accessible by Replicate")

    if not prompt.strip():
        raise ValueError("Replicate prompt is required")

    if duration < 1 or duration > 15:
        raise ValueError("duration must be between 1 and 15 seconds")

    if resolution not in {"720p", "480p"}:
        raise ValueError("resolution must be either 720p or 480p")

    if aspect_ratio not in {"auto", "16:9", "4:3", "1:1", "9:16", "3:4", "3:2", "2:3"}:
        raise ValueError("Unsupported aspect_ratio")

    owner, model_name = model.strip().split("/", 1)
    safe_image_field = image_field.strip() or "start_image"

    payload: dict[str, Any] = {
        "input": {
            safe_image_field: image_url.strip(),
            "prompt": prompt.strip(),
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        }
    }

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Prefer": f"wait={wait_seconds}",
    }

    async with httpx.AsyncClient(timeout=max(90, wait_seconds + 30)) as client:
        response = await client.post(
            f"{REPLICATE_API_BASE_URL}/models/{owner}/{model_name}/predictions",
            json=payload,
            headers=headers,
        )

    response.raise_for_status()

    data = response.json()
    if not isinstance(data, Mapping):
        raise RuntimeError("Unexpected Replicate response")

    return data


async def get_prediction(*, api_token: str, prediction_id: str) -> Mapping[str, Any]:
    headers = {"Authorization": f"Bearer {api_token}"}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{REPLICATE_API_BASE_URL}/predictions/{prediction_id}", headers=headers)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping):
        raise RuntimeError("Unexpected Replicate prediction response")
    return data


async def wait_for_prediction_output(
    *,
    api_token: str,
    prediction: Mapping[str, Any],
    timeout_seconds: int = 240,
    poll_interval_seconds: int = 5,
) -> Mapping[str, Any]:
    prediction_id = extract_replicate_prediction_id(prediction)
    if not prediction_id or extract_replicate_video_url(prediction):
        return prediction

    current = prediction
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        status = str(current.get("status") or "").lower()
        if status in {"succeeded", "failed", "canceled"}:
            return current
        await asyncio.sleep(poll_interval_seconds)
        current = await get_prediction(api_token=api_token, prediction_id=prediction_id)
        if extract_replicate_video_url(current):
            return current
    return current


def extract_replicate_prediction_id(payload: Mapping[str, Any]) -> str | None:
    for key in ("id", "prediction_id", "predictionId"):
        value = payload.get(key)
        if value:
            return str(value)
    prediction = payload.get("prediction")
    if isinstance(prediction, Mapping):
        return extract_replicate_prediction_id(prediction)
    return None


def extract_replicate_video_url(payload: Mapping[str, Any]) -> str | None:
    for key in ("video", "video_url", "videoUrl", "url"):
        value = payload.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    output = payload.get("output")
    if isinstance(output, str) and output.startswith("http"):
        return output
    if isinstance(output, list):
        for item in output:
            if isinstance(item, str) and item.startswith("http"):
                return item
            if isinstance(item, Mapping):
                nested = extract_replicate_video_url(item)
                if nested:
                    return nested
    if isinstance(output, Mapping):
        return extract_replicate_video_url(output)
    return None
