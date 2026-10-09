"""Thin wrapper around the Groq chat API.

All LLM traffic goes through `ask_json()`, so swapping provider (OpenAI,
Claude, a local model) means editing this one file. Both of our prompts ask
for a JSON object, because structured output is what lets the Python code
check the answer before a visitor ever sees it.
"""

import json
import logging

from groq import APIError, Groq, RateLimitError

from app import config

log = logging.getLogger(__name__)


class LLMError(Exception):
    """The LLM could not be reached or did not return usable JSON."""


_client: Groq | None = None


def _get_client() -> Groq:
    """Create the Groq client on first use (so the app can still start, and
    explain the problem, when the API key is missing)."""
    global _client
    if not config.GROQ_API_KEY:
        raise LLMError("GROQ_API_KEY is not set")
    if _client is None:
        # The SDK itself retries rate-limit (429) and server errors with
        # back-off, which matters on a free tier.
        _client = Groq(api_key=config.GROQ_API_KEY, max_retries=1, timeout=30)
    return _client


def ask_json(model: str, system_prompt: str, user_prompt: str, max_tokens: int = 2000) -> dict:
    """Send one system + user message and return the reply parsed as a dict.

    If `model` is rate limited (free-tier quota used up), the models in
    config.FALLBACK_MODELS are tried in order.

    `max_tokens` covers the model's hidden reasoning AND the visible JSON, so
    it is set generously; a limit that is too low makes JSON mode fail.
    """
    # Only send the reasoning setting when one is configured, because models
    # without a reasoning mode reject the parameter.
    extra = {"reasoning_effort": config.REASONING_EFFORT} if config.REASONING_EFFORT else {}
    candidates = [model] + [m for m in config.FALLBACK_MODELS if m != model]

    for position, candidate in enumerate(candidates):
        try:
            completion = _get_client().chat.completions.create(
                **extra,
                model=candidate,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,  # as repeatable as the model allows
                max_tokens=max_tokens,
                response_format={"type": "json_object"},  # Groq "JSON mode"
            )
            reply = json.loads(completion.choices[0].message.content)
        except RateLimitError as error:
            # Quota for this model is exhausted -> try the next model, if any.
            failure = f"{candidate} is rate limited"
            last_error = error
        except APIError as error:
            # "json_validate_failed" means the model wrote something that was
            # not valid JSON (seen occasionally in testing). Another model, or
            # simply another attempt, usually succeeds, so move on. Any other
            # API error (bad key, bad request) will not fix itself: stop.
            if "json_validate_failed" not in str(error):
                log.error("Groq API error (%s): %s", candidate, error)
                raise LLMError(str(error)) from error
            failure = f"{candidate} returned invalid JSON"
            last_error = error
        except (json.JSONDecodeError, TypeError, IndexError) as error:
            failure = f"{candidate} returned invalid JSON"
            last_error = error
        else:
            failure = ""

        if failure:
            if position + 1 < len(candidates):
                log.warning("%s, falling back to %s", failure, candidates[position + 1])
                continue
            log.error("Every configured model failed; last error: %s", last_error)
            raise LLMError(f"all models failed ({failure})") from last_error

        if not isinstance(reply, dict):
            raise LLMError("Model returned JSON that is not an object")
        reply["_model"] = candidate  # record which model actually answered
        return reply

    raise LLMError("no model configured")
