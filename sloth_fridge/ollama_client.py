from __future__ import annotations

from typing import Any

import requests

from . import config


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, host: str | None = None, timeout: int | None = None):
        self.host = (host or config.OLLAMA_HOST).rstrip("/")
        self.timeout = timeout or config.REQUEST_TIMEOUT
        self.session = requests.Session()

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self.host}{path}"
        try:
            response = self.session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise OllamaError(f"cannot reach Ollama at {self.host}: {exc}") from exc
        if response.status_code >= 400:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:400]}")
        try:
            return response.json()
        except ValueError as exc:
            raise OllamaError(f"Ollama returned invalid JSON: {response.text[:200]}") from exc

    def _get(self, path: str) -> Any:
        try:
            response = self.session.get(f"{self.host}{path}", timeout=15)
        except requests.RequestException as exc:
            raise OllamaError(f"cannot reach Ollama at {self.host}: {exc}") from exc
        if response.status_code >= 400:
            raise OllamaError(f"Ollama HTTP {response.status_code}: {response.text[:300]}")
        return response.json()

    def version(self) -> str:
        return self._get("/api/version").get("version", "unknown")

    def list_models(self) -> list[str]:
        data = self._get("/api/tags")
        return sorted(model.get("name", "") for model in data.get("models", []))

    def has_model(self, model: str) -> bool:
        base = model.split(":")[0]
        return any(name == model or name.split(":")[0] == base for name in self.list_models())

    def chat(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        images: list[str] | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.0,
        num_predict: int | None = None,
        json_mode: bool = False,
        options: dict | None = None,
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt, "images": images or []})
        merged_options: dict = {"temperature": temperature}
        if num_predict:
            merged_options["num_predict"] = num_predict
        if options:
            merged_options.update(options)
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": merged_options,
        }
        if json_schema:
            payload["format"] = json_schema
        elif json_mode:
            payload["format"] = "json"
        data = self._post("/api/chat", payload)
        return (data.get("message") or {}).get("content", "") or ""

    def chat_json(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        images: list[str] | None = None,
        json_schema: dict | None = None,
        temperature: float = 0.0,
    ) -> dict | list:
        from .imaging import extract_json

        if json_schema:
            try:
                raw = self.chat(model, prompt, system=system, images=images, json_schema=json_schema, temperature=temperature)
                parsed = extract_json(raw)
                if parsed is not None:
                    return parsed
            except OllamaError:
                pass
        raw = self.chat(model, prompt, system=system, images=images, json_schema=None, temperature=temperature, json_mode=True)
        parsed = extract_json(raw)
        if parsed is None:
            raise OllamaError(f"model did not return usable JSON: {raw[:200]}")
        return parsed
