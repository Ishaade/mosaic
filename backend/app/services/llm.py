"""
Thin wrapper around the OpenAI-compatible chat API (Groq today).

All provider details stay here so swapping vendors means editing this file
(and .env), not the routers.
"""

import asyncio
import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Create ONE client and reuse it. Creating one per request wastes connections.
# AsyncOpenAI = the version whose calls we can `await`.
client = AsyncOpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)

# How many times to retry on rate-limit / server errors before giving up.
_MAX_RETRIES = 3
# Base delay in seconds; doubles each attempt (1s, 2s, 4s).
_BACKOFF_BASE_SECONDS = 1.0


class LLMError(Exception):
    """Clean failure the router can turn into an HTTP response (no secrets)."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _map_status_to_client_error(status_code: int) -> tuple[int, str]:
    """Turn provider HTTP codes into safe messages for our API clients."""
    if status_code == 401:
        return 502, "The AI provider rejected our credentials. Please try again later."
    if status_code == 404:
        return 502, "The configured AI model was not found. Please try again later."
    if status_code == 429:
        return 503, "The AI provider is rate-limiting us. Please wait a moment and retry."
    if status_code >= 500:
        return 503, "The AI provider is temporarily unavailable. Please try again later."
    return 502, "The AI provider returned an unexpected error. Please try again later."


async def complete_chat(
    system_prompt: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
) -> str:
    """
    Low-level chat completion with retries.

    Used by generate_reply (user-facing chat) and by memory extraction.
    `messages` is a list of {"role": "user"|"assistant", "content": "..."}.
    """
    api_messages = [{"role": "system", "content": system_prompt}, *messages]

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=api_messages,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMError(502, "The AI provider returned an empty reply.")
            return content

        except LLMError:
            raise

        except APITimeoutError as exc:
            last_error = exc
            logger.warning("LLM timeout (attempt %s/%s)", attempt + 1, _MAX_RETRIES)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            raise LLMError(504, "The AI provider timed out. Please try again.") from exc

        except APIConnectionError as exc:
            last_error = exc
            logger.warning("LLM connection error (attempt %s/%s)", attempt + 1, _MAX_RETRIES)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            raise LLMError(
                503, "Could not reach the AI provider. Please try again later."
            ) from exc

        except APIStatusError as exc:
            last_error = exc
            status = exc.status_code
            if status == 429 or status >= 500:
                logger.warning(
                    "LLM status %s (attempt %s/%s)", status, attempt + 1, _MAX_RETRIES
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                    continue
            http_status, detail = _map_status_to_client_error(status)
            raise LLMError(http_status, detail) from exc

        except Exception as exc:
            logger.exception("Unexpected LLM error")
            raise LLMError(
                502, "Something went wrong talking to the AI provider."
            ) from exc

    raise LLMError(502, "The AI provider failed after retries.") from last_error


async def generate_reply(
    system_prompt: str,
    messages: list[dict[str, str]],
) -> str:
    """The chat-path helper: slightly higher temperature for natural replies."""
    return await complete_chat(system_prompt, messages, temperature=0.7)


async def stream_reply(
    system_prompt: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
):
    """
    Yield text deltas as the provider streams them (for SSE).

    Trade-off vs complete_chat: we do not retry mid-stream — a dropped
    connection surfaces as an error event to the client instead.
    """
    api_messages = [{"role": "system", "content": system_prompt}, *messages]
    try:
        stream = await client.chat.completions.create(
            model=settings.llm_model,
            messages=api_messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    except APITimeoutError as exc:
        raise LLMError(504, "The AI provider timed out. Please try again.") from exc
    except APIConnectionError as exc:
        raise LLMError(
            503, "Could not reach the AI provider. Please try again later."
        ) from exc
    except APIStatusError as exc:
        http_status, detail = _map_status_to_client_error(exc.status_code)
        raise LLMError(http_status, detail) from exc
    except LLMError:
        raise
    except Exception as exc:
        logger.exception("Unexpected LLM stream error")
        raise LLMError(
            502, "Something went wrong talking to the AI provider."
        ) from exc
