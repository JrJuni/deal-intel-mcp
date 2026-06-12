"""LLM provider abstraction — ported from event-intel-mcp.

Changes from original:
  - _TOKEN_PATH: ~/.event-intel/ → ~/.deal-intel/
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class LLMResponse:
    text: str
    usage: dict[str, int]
    model: str
    stop_reason: str | None = None


class LLMProvider(ABC):
    @abstractmethod
    def chat_cached(
        self,
        *,
        system: str,
        cached_context: str,
        volatile_context: str,
        task: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse: ...

    @abstractmethod
    def chat_once(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse: ...

    @abstractmethod
    def ping(self) -> dict: ...


class AnthropicProvider(LLMProvider):
    """Default LLMProvider using anthropic SDK. anthropic is imported lazily."""

    def __init__(self, *, model: str = "claude-sonnet-4-6", api_key: str | None = None) -> None:
        self.model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client = None

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic

            if not self._api_key:
                raise RuntimeError("ANTHROPIC_API_KEY not set")
            self._client = Anthropic(api_key=self._api_key)
        return self._client

    def chat_cached(
        self,
        *,
        system: str,
        cached_context: str,
        volatile_context: str,
        task: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        client = self._get_client()
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": cached_context,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {"type": "text", "text": volatile_context} if volatile_context else None,
                    {"type": "text", "text": task},
                ],
            }
        ]
        messages[0]["content"] = [c for c in messages[0]["content"] if c is not None]
        resp = client.messages.create(
            model=self.model,
            system=system,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return LLMResponse(
            text=text,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
                "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
                "cache_creation_input_tokens": getattr(
                    resp.usage, "cache_creation_input_tokens", 0
                )
                or 0,
            },
            model=resp.model,
            stop_reason=resp.stop_reason,
        )

    def chat_once(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        client = self._get_client()
        resp = client.messages.create(
            model=self.model,
            system=system,
            messages=[{"role": "user", "content": user}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        return LLMResponse(
            text=text,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
            model=resp.model,
            stop_reason=resp.stop_reason,
        )

    def ping(self) -> dict:
        if not self._api_key:
            return {
                "status": "missing_key",
                "message": "ANTHROPIC_API_KEY not set",
                "fix": "Set ANTHROPIC_API_KEY in .env (see .env.example)",
            }
        return {"status": "ok", "model": self.model}


class ChatGPTOAuthProvider(LLMProvider):
    """LLMProvider via ChatGPT Plus/Pro subscription — OAuth 2.0 PKCE flow.

    Uses the same auth.openai.com endpoint as the Codex CLI.
    On first use (or after token expiry), opens a browser for login.
    Tokens are cached at ~/.deal-intel/chatgpt_auth.json and auto-refreshed.

    NOTE: This uses an unofficial path (Codex CLI client_id). OpenAI may change
    it. Intended for personal local use only — do not deploy as a shared server.
    Calls the OpenAI Responses API, not chat/completions.
    """

    _CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
    _AUTH_URL = "https://auth.openai.com/oauth/authorize"
    _TOKEN_URL = "https://auth.openai.com/oauth/token"
    _REDIRECT_URI = "http://localhost:1455/auth/callback"
    _RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
    _TOKEN_PATH = Path.home() / ".deal-intel" / "chatgpt_auth.json"
    _ALLOWED_REASONING_EFFORTS = frozenset({"low", "medium", "high"})

    def __init__(self, *, model: str = "gpt-5.5", reasoning_effort: str = "low") -> None:
        if reasoning_effort not in self._ALLOWED_REASONING_EFFORTS:
            raise ValueError(
                f"reasoning_effort must be one of {sorted(self._ALLOWED_REASONING_EFFORTS)}, "
                f"got {reasoning_effort!r}"
            )
        self.model = model
        self._reasoning_effort = reasoning_effort
        self._tokens: dict | None = None

    # ---- token persistence ----

    def _load_tokens(self) -> dict | None:
        if self._TOKEN_PATH.exists():
            try:
                import json
                return json.loads(self._TOKEN_PATH.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None

    def _save_tokens(self, tokens: dict) -> None:
        import json
        self._TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._TOKEN_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")

    def _is_token_valid(self, tokens: dict) -> bool:
        import time
        return time.time() < tokens.get("expires_at", 0) - 60

    def _refresh(self, refresh_token: str) -> dict | None:
        import time

        import httpx
        try:
            resp = httpx.post(
                self._TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._CLIENT_ID,
                    "refresh_token": refresh_token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                data["expires_at"] = time.time() + data.get("expires_in", 3600)
                return data
        except Exception:
            pass
        return None

    # ---- PKCE login ----

    def _pkce_login(self) -> dict:
        import base64
        import hashlib
        import secrets
        import threading
        import time
        import urllib.parse
        import webbrowser
        from http.server import BaseHTTPRequestHandler, HTTPServer

        code_verifier = secrets.token_urlsafe(96)[:128]
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )

        auth_code: dict[str, str] = {}

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                if "code" in params:
                    auth_code["value"] = params["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    b"<html><body>Authenticated. You can close this tab.</body></html>"
                )

            def log_message(self, *args: object) -> None:
                pass

        server = HTTPServer(("localhost", 1455), _Handler)
        t = threading.Thread(target=server.handle_request, daemon=True)
        t.start()

        state = secrets.token_urlsafe(32)
        qs = urllib.parse.urlencode({
            "response_type": "code",
            "client_id": self._CLIENT_ID,
            "redirect_uri": self._REDIRECT_URI,
            "scope": (
                "openid profile email offline_access "
                "api.connectors.read api.connectors.invoke"
            ),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "state": state,
            "originator": "codex_cli_rs",
        })
        auth_url = f"{self._AUTH_URL}?{qs}"
        print(f"\nOpening browser for ChatGPT login...\n{auth_url}\n")
        webbrowser.open(auth_url)

        t.join(timeout=120)
        server.server_close()

        if "value" not in auth_code:
            raise RuntimeError("ChatGPT OAuth login timed out or was cancelled")

        import httpx
        resp = httpx.post(
            self._TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self._CLIENT_ID,
                "code": auth_code["value"],
                "code_verifier": code_verifier,
                "redirect_uri": self._REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        tokens = resp.json()
        tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
        return tokens

    # ---- token management ----

    def _ensure_token(self) -> str:
        if self._tokens is None:
            self._tokens = self._load_tokens()

        if self._tokens and self._is_token_valid(self._tokens):
            return self._tokens["access_token"]

        if self._tokens and self._tokens.get("refresh_token"):
            refreshed = self._refresh(self._tokens["refresh_token"])
            if refreshed:
                self._tokens = refreshed
                self._save_tokens(self._tokens)
                return self._tokens["access_token"]

        self._tokens = self._pkce_login()
        self._save_tokens(self._tokens)
        return self._tokens["access_token"]

    def login(self, *, force: bool = False) -> dict:
        """Deliberate terminal-driven OAuth login. Returns status dict (no secrets)."""
        if force:
            self._tokens = self._pkce_login()
            self._save_tokens(self._tokens)
        else:
            self._ensure_token()
        return {"status": "ok", "model": self.model, "token_path": str(self._TOKEN_PATH)}

    # ---- JWT account_id extraction ----

    @staticmethod
    def _decode_account_id(access_token: str) -> str:
        import base64
        import json
        try:
            payload_b64 = access_token.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            return payload["https://api.openai.com/auth"]["chatgpt_account_id"]
        except Exception as exc:
            raise RuntimeError(
                f"Could not extract chatgpt_account_id from token: {exc}. "
                "Delete ~/.deal-intel/chatgpt_auth.json and re-authenticate."
            ) from exc

    # ---- Responses API call (SSE) ----

    def _call(
        self,
        *,
        instructions: str,
        user_content: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import json

        import httpx

        token = self._ensure_token()
        account_id = self._decode_account_id(token)

        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_content}],
                }
            ],
            "store": False,
            "stream": True,
            "reasoning": {"effort": self._reasoning_effort, "summary": "auto"},
        }
        # max_tokens and temperature intentionally omitted —
        # Codex backend rejects them with 400 Unsupported parameter (verified 2026-05-29).
        _ = max_tokens
        _ = temperature
        headers = {
            "Authorization": f"Bearer {token}",
            "chatgpt-account-id": account_id,
            "OpenAI-Beta": "responses=experimental",
            "originator": "codex_cli_rs",
            "OAI-Product-Sku": "codex",
            "Content-Type": "application/json",
            "accept": "text/event-stream",
        }

        text_parts: list[str] = []
        input_tokens = 0
        output_tokens = 0
        final_model = self.model
        stop_reason: str | None = None
        seen_completed = False
        seen_error_payload: object | None = None

        with httpx.stream(
            "POST", self._RESPONSES_URL, headers=headers, json=payload, timeout=120
        ) as resp:
            if resp.status_code != 200:
                body = resp.read().decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"ChatGPT backend returned {resp.status_code}: {body[:500]}"
                )
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].lstrip()
                if raw == "[DONE]":
                    break
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                etype = event.get("type", "")
                if etype == "response.output_text.delta":
                    text_parts.append(event.get("delta", ""))
                elif etype == "response.completed":
                    seen_completed = True
                    final = event.get("response", {})
                    final_model = final.get("model", final_model)
                    usage = final.get("usage", {}) or {}
                    input_tokens = usage.get("input_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0)
                    stop_reason = final.get("status", "completed")
                    if not text_parts:
                        for item in final.get("output", []):
                            if item.get("type") == "message":
                                for block in item.get("content", []):
                                    if block.get("type") == "output_text":
                                        text_parts.append(block.get("text", ""))
                elif etype in ("response.failed", "response.error", "response.incomplete"):
                    seen_error_payload = (
                        event.get("error")
                        or event.get("response", {}).get("error")
                        or event.get("response", {}).get("status")
                        or event
                    )
                    break

        if seen_error_payload is not None:
            raise RuntimeError(
                f"ChatGPT backend reported error event: {seen_error_payload!r}"
            )
        if not seen_completed:
            raise RuntimeError(
                "ChatGPT backend returned an incomplete stream "
                "(no response.completed event before close)."
            )

        return LLMResponse(
            text="".join(text_parts),
            usage={"input_tokens": input_tokens, "output_tokens": output_tokens},
            model=final_model,
            stop_reason=stop_reason,
        )

    # ---- LLMProvider interface ----

    def chat_once(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return self._call(
            instructions=system,
            user_content=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def chat_cached(
        self,
        *,
        system: str,
        cached_context: str,
        volatile_context: str,
        task: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        # Responses API has no prompt caching — concatenate contexts
        parts = [p for p in (cached_context, volatile_context, task) if p]
        return self._call(
            instructions=system,
            user_content="\n\n".join(parts),
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def ping(self) -> dict:
        tokens = self._load_tokens()
        if tokens is None:
            return {
                "status": "not_logged_in",
                "message": "ChatGPT OAuth not authenticated",
                "fix": "Run `deal-intel login-chatgpt` once in a terminal to authenticate.",
            }
        if self._is_token_valid(tokens) or tokens.get("refresh_token"):
            return {"status": "ok", "model": self.model}
        return {
            "status": "not_logged_in",
            "message": "ChatGPT OAuth token expired and no refresh token",
            "fix": "Run `deal-intel login-chatgpt --force` to re-authenticate.",
        }


class OpenAIAPIProvider(LLMProvider):
    """Official OpenAI API provider using the Responses API."""

    _RESPONSES_URL = "https://api.openai.com/v1/responses"
    _ALLOWED_REASONING_EFFORTS = frozenset({"none", "low", "medium", "high", "xhigh"})

    def __init__(
        self,
        *,
        model: str = "gpt-5.4-mini",
        api_key: str | None = None,
        reasoning_effort: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if reasoning_effort in ("", "none", "null"):
            reasoning_effort = None
        if (
            reasoning_effort is not None
            and reasoning_effort not in self._ALLOWED_REASONING_EFFORTS
        ):
            raise ValueError(
                "openai_api_reasoning_effort must be one of "
                f"{sorted(self._ALLOWED_REASONING_EFFORTS)}, got {reasoning_effort!r}"
            )
        self.model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._reasoning_effort = reasoning_effort
        self._responses_url = (base_url or self._RESPONSES_URL).rstrip("/")

    def _call(
        self,
        *,
        instructions: str,
        user_content: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        import httpx

        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": instructions,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_content}],
                }
            ],
            "max_output_tokens": max_tokens,
            "store": False,
            "temperature": temperature,
        }
        if self._reasoning_effort is not None:
            payload["reasoning"] = {"effort": self._reasoning_effort}

        resp = httpx.post(
            self._responses_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"OpenAI API returned {resp.status_code}: {_response_error_message(resp)}"
            )

        data = resp.json()
        if data.get("error"):
            raise RuntimeError(f"OpenAI API returned error: {data['error']!r}")
        if data.get("status") not in (None, "completed"):
            details = data.get("incomplete_details") or data.get("status")
            raise RuntimeError(f"OpenAI API response did not complete: {details!r}")

        text = _extract_openai_output_text(data)
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            usage={
                "input_tokens": int(usage.get("input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
                "cached_input_tokens": int(
                    (usage.get("input_tokens_details") or {}).get("cached_tokens") or 0
                ),
                "reasoning_output_tokens": int(
                    (usage.get("output_tokens_details") or {}).get("reasoning_tokens") or 0
                ),
            },
            model=data.get("model", self.model),
            stop_reason=data.get("status"),
        )

    def chat_once(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        return self._call(
            instructions=system,
            user_content=user,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def chat_cached(
        self,
        *,
        system: str,
        cached_context: str,
        volatile_context: str,
        task: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> LLMResponse:
        # The Responses API supports prompt caching at the platform/model layer,
        # but this provider keeps the project-level contract provider-neutral.
        parts = [part for part in (cached_context, volatile_context, task) if part]
        return self._call(
            instructions=system,
            user_content="\n\n".join(parts),
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def ping(self) -> dict:
        if not self._api_key:
            return {
                "status": "missing_key",
                "message": "OPENAI_API_KEY not set",
                "fix": "Set OPENAI_API_KEY in .env or ~/.deal-intel/config.yaml.",
            }
        return {"status": "ok", "model": self.model}


def make_llm_provider(config: dict, *, model: str | None = None) -> LLMProvider:
    """Factory: reads llm.provider from config and returns the right provider."""
    provider_name = config.get("llm", {}).get("provider", "anthropic")
    if provider_name == "chatgpt_oauth":
        oauth_model = config.get("llm", {}).get("chatgpt_oauth_model", "gpt-5.5")
        effort = config.get("llm", {}).get("chatgpt_oauth_reasoning_effort", "low")
        return ChatGPTOAuthProvider(model=oauth_model, reasoning_effort=effort)
    if provider_name == "openai_api":
        openai_model = model or config.get("llm", {}).get("openai_api_model", "gpt-5.4-mini")
        effort = config.get("llm", {}).get("openai_api_reasoning_effort")
        return OpenAIAPIProvider(model=openai_model, reasoning_effort=effort)
    resolved = model or config.get("llm", {}).get("draft_model", "claude-sonnet-4-6")
    return AnthropicProvider(model=resolved)


def _extract_openai_output_text(data: dict) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text

    text_parts: list[str] = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for block in item.get("content", []) or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "output_text":
                text_parts.append(str(block.get("text") or ""))
    return "".join(text_parts)


def _response_error_message(resp: Any) -> str:
    try:
        payload = resp.json()
    except Exception:
        return resp.text[:500]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error)
        if error:
            return str(error)
    return str(payload)[:500]
