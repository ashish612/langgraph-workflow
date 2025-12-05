"""
Custom LangChain LLM wrapper for Cisco Bridge API (GPT-4o-mini).

This module provides a LangChain-compatible chat model that uses
Cisco's Bridge API to access GPT-4o-mini.
"""

import base64
import requests
from typing import Any, List, Optional, Iterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    AIMessageChunk,
)
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, SecretStr
import threading
import time


class CiscoBridgeChatModel(BaseChatModel):
    """
    LangChain Chat Model wrapper for Cisco Bridge API.

    Uses OAuth2 client credentials flow to obtain access token,
    then calls the GPT-4o-mini endpoint.
    """

    client_id: str = Field(..., description="Cisco OAuth2 client ID")
    client_secret: SecretStr = Field(..., description="Cisco OAuth2 client secret")
    app_key: str = Field(..., description="Bridge API app key")

    # API endpoints
    token_url: str = Field(
        default="https://id.cisco.com/oauth2/default/v1/token",
        description="OAuth2 token endpoint",
    )
    api_url: str = Field(
        default="https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions",
        description="Chat completions API endpoint",
    )

    # Model parameters
    temperature: float = Field(default=0.7, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens to generate")
    stop_sequences: List[str] = Field(
        default_factory=lambda: ["<|im_end|>"],
        description="Stop sequences",
    )

    # Token caching
    _access_token: Optional[str] = None
    _token_expiry: float = 0
    _token_lock: threading.Lock = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, "_access_token", None)
        object.__setattr__(self, "_token_expiry", 0)
        object.__setattr__(self, "_token_lock", threading.Lock())

    @property
    def _llm_type(self) -> str:
        return "cisco-bridge-gpt4o-mini"

    @property
    def _identifying_params(self) -> dict:
        return {
            "model": "gpt-4o-mini",
            "temperature": self.temperature,
            "api_url": self.api_url,
        }

    def _get_access_token(self) -> str:
        """
        Obtain OAuth2 access token using client credentials flow.
        Caches the token and refreshes when expired.
        """
        with self._token_lock:
            # Check if we have a valid cached token
            if self._access_token and time.time() < self._token_expiry:
                return self._access_token

            # Request new token
            payload = "grant_type=client_credentials"
            credentials = f"{self.client_id}:{self.client_secret.get_secret_value()}"
            encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")

            headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {encoded_credentials}",
            }

            response = requests.post(self.token_url, headers=headers, data=payload)
            response.raise_for_status()

            token_data = response.json()
            access_token = token_data.get("access_token")
            object.__setattr__(self, "_access_token", access_token)

            # Set expiry (default 1 hour minus 5 minutes buffer)
            expires_in = token_data.get("expires_in", 3600)
            object.__setattr__(self, "_token_expiry", time.time() + expires_in - 300)

            return access_token

    def _convert_messages(self, messages: List[BaseMessage]) -> List[dict]:
        """Convert LangChain messages to API format."""
        converted = []
        for message in messages:
            if isinstance(message, SystemMessage):
                converted.append({"role": "system", "content": message.content})
            elif isinstance(message, HumanMessage):
                converted.append({"role": "user", "content": message.content})
            elif isinstance(message, AIMessage):
                converted.append({"role": "assistant", "content": message.content})
            else:
                # Default to user message
                converted.append({"role": "user", "content": str(message.content)})
        return converted

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate a response using Cisco Bridge API."""
        access_token = self._get_access_token()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": access_token,
        }

        # Build request payload
        payload = {
            "messages": self._convert_messages(messages),
            "user": f'{{"appkey": "{self.app_key}"}}',
            "temperature": self.temperature,
        }

        # Add stop sequences
        stop_seqs = stop or self.stop_sequences
        if stop_seqs:
            payload["stop"] = stop_seqs

        # Add max_tokens if specified
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens

        # Make API request
        response = requests.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()

        # Parse response
        choice = result["choices"][0]
        message_content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason", "stop")

        # Build ChatResult
        generation = ChatGeneration(
            message=AIMessage(content=message_content),
            generation_info={"finish_reason": finish_reason},
        )

        return ChatResult(
            generations=[generation],
            llm_output={
                "model": "gpt-4o-mini",
                "usage": result.get("usage", {}),
            },
        )

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generation - falls back to sync for now."""
        # For simplicity, use sync version
        # Could be enhanced with httpx for true async
        return self._generate(messages, stop, run_manager, **kwargs)


def create_cisco_bridge_llm(
    client_id: str,
    client_secret: str,
    app_key: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None,
) -> CiscoBridgeChatModel:
    """
    Factory function to create a Cisco Bridge LLM instance.

    Args:
        client_id: Cisco OAuth2 client ID
        client_secret: Cisco OAuth2 client secret
        app_key: Bridge API app key
        temperature: Sampling temperature (default 0.7)
        max_tokens: Maximum tokens to generate (optional)

    Returns:
        Configured CiscoBridgeChatModel instance
    """
    return CiscoBridgeChatModel(
        client_id=client_id,
        client_secret=SecretStr(client_secret),
        app_key=app_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )

