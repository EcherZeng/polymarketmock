"""LLM client — httpx wrapper for OpenAI-compatible chat completion."""

from __future__ import annotations

import httpx


async def call_llm(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """Call OpenAI-compatible chat completion endpoint using a shared client."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "response_format": {"type": "json_object"},
    }

    resp = await client.post(api_url, json=payload, headers=headers)
    resp.raise_for_status()

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return content
