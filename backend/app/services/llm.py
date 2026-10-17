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


async def generate_reply(
    system_prompt: str,
    messages: list[dict[str, str]],
) -> str:
    """
    The ONLY function in the app that talks to the LLM provider.

    `messages` is a list of {"role": "user"|"assistant", "content": "..."}
    already trimmed to our history budget by the caller.
    """
    api_messages = [{"role": "system", "content": system_prompt}, *messages]

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=api_messages,
            )
            # The reply text lives inside the first "choice"
            content = response.choices[0].message.content
            if not content:
                raise LLMError(502, "The AI provider returned an empty reply.")
            return content

        except LLMError:
            raise

        except APITimeoutError as exc:
            last_error = exc
            logger.warning("LLM timeout (attempt %s/%s)", attempt + 1, _MAX_RETRIES)
            # Timeouts: retry with backoff — often transient
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
            # Retry only rate-limits and server errors — 4xx (except 429) won't help
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
            # Catch-all: never leak traceback or keys to the client
            logger.exception("Unexpected LLM error")
            raise LLMError(
                502, "Something went wrong talking to the AI provider."
            ) from exc

    # Should be unreachable, but keeps type-checkers happy
    raise LLMError(502, "The AI provider failed after retries.") from last_error
