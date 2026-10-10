from openai import AsyncOpenAI

from app.config import settings

# Create ONE client and reuse it. Creating one per request wastes connections.
# AsyncOpenAI = the version whose calls we can `await`.
client = AsyncOpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)


async def generate_reply(system_prompt: str, user_message: str) -> str:
    """The ONLY function in the app that talks to the LLM provider."""
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            # "system" sets the rules and personality; "user" is what they typed
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    # The reply text lives inside the first "choice"
    return response.choices[0].message.content