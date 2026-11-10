import os
import re
import json
import time
import random
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from core.config import (
    ALPME_BASE_URL,
    ALPME_API_KEY,
    DEFAULT_MODEL,
    FALLBACK_OPENAI_API_KEY,
    FALLBACK_OPENAI_BASE_URL,
)

logger = logging.getLogger("ShadowBrowser.LLMClient")

class LLMClient:
    """
    Robust LLM client targeting Alpme gateway (https://alpme.com/v1) with
    exponential backoff retry for 503 high load and configurable fallback providers.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 4,
    ):
        self.api_key = api_key or ALPME_API_KEY or os.getenv("ALPME_API_KEY", "")
        self.base_url = base_url or ALPME_BASE_URL
        self.model = model or DEFAULT_MODEL
        self.max_retries = max_retries

        self._client: Optional[OpenAI] = None
        self._init_client()

    def _init_client(self):
        """Initializes the OpenAI SDK client configured for Alpme gateway."""
        if not self.api_key:
            logger.warning("No ALPME_API_KEY found in environment or arguments.")

        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "sk-dummy",
            timeout=40.0,
        )

    def list_available_models(self) -> List[str]:
        """Queries Alpme gateway for list of supported models."""
        try:
            res = self._client.models.list()
            return [m.id for m in res.data]
        except Exception as e:
            logger.warning(f"Could not fetch models from gateway: {e}")
            return [
                "gemini-3.8-flash",
                "gemini-3.7-flash",
                "gpt-5.6-terra",
                "gpt-6-sol",
                "deepseek-v4.1-flash-1017",
                "claude-sonnet-4-6",
                "qwen3.8-flash",
            ]

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.2,
        max_tokens: int = 1500,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Executes a chat completion with retry backoff for server overload.
        """
        last_error = None
        delay = 1.5

        for attempt in range(1, self.max_retries + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if response_format:
                    kwargs["response_format"] = response_format

                response = self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                return content.strip()

            except Exception as e:
                err_str = str(e)
                last_error = e
                logger.warning(f"[Attempt {attempt}/{self.max_retries}] Gateway error: {err_str}")

                # If server overload 503, apply exponential backoff + jitter
                if "503" in err_str or "server_overloaded" in err_str or "rate_limit" in err_str.lower():
                    sleep_time = delay + random.uniform(0.5, 1.5)
                    logger.info(f"Retrying in {sleep_time:.2f}s due to gateway load...")
                    time.sleep(sleep_time)
                    delay *= 2
                else:
                    time.sleep(1.0)

        # Check if fallback provider is configured
        if FALLBACK_OPENAI_API_KEY:
            logger.info("Attempting fallback OpenAI provider...")
            try:
                fallback_client = OpenAI(
                    base_url=FALLBACK_OPENAI_BASE_URL or "https://api.openai.com/v1",
                    api_key=FALLBACK_OPENAI_API_KEY,
                )
                response = fallback_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return (response.choices[0].message.content or "").strip()
            except Exception as fe:
                logger.error(f"Fallback provider failed: {fe}")

        raise RuntimeError(f"LLM call failed after {self.max_retries} attempts. Last error: {last_error}")

    def structured_action(
        self,
        system_prompt: str,
        user_prompt: str,
        image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Requests structured JSON action plan from the model and parses output safely.
        """
        messages = [{"role": "system", "content": system_prompt}]

        if image_base64:
            # Multi-modal prompt if vision model is available
            user_content = [
                {"type": "text", "text": user_prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                },
            ]
            messages.append({"role": "user", "content": user_content})
        else:
            messages.append({"role": "user", "content": user_prompt})

        raw_reply = self.chat_completion(messages, temperature=0.1)

        # Extract JSON from Markdown code blocks if present
        clean_json = raw_reply
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_reply)
        if json_match:
            clean_json = json_match.group(1)

        try:
            return json.loads(clean_json)
        except Exception:
            # Fallback regex search for json object
            obj_match = re.search(r"(\{[\s\S]*\})", raw_reply)
            if obj_match:
                try:
                    return json.loads(obj_match.group(1))
                except Exception:
                    pass
            logger.warning(f"Failed to parse JSON from LLM reply: {raw_reply[:200]}")
            return {
                "thought": "Failed to parse JSON response from LLM.",
                "action": "wait",
                "seconds": 2,
                "raw": raw_reply,
            }
