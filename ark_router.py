from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from openai import APIStatusError, OpenAI


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


@dataclass
class ModelConfig:
    name: str
    ep_id: str
    ark_api_key: str
    usable: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelConfig":
        return cls(
            name=data["name"],
            ep_id=data["ep_id"],
            ark_api_key=data["ark_api_key"],
            usable=bool(data.get("usable", True)),
        )


class ArkModelRouter:
    def __init__(
        self,
        model_configs: Iterable[Dict[str, Any] | ModelConfig],
        *,
        base_url: str = DEFAULT_BASE_URL,
        status_file: str | os.PathLike[str] = "model_status.json",
        persist_status: bool = True,
    ) -> None:
        self.base_url = base_url
        self.persist_status = persist_status
        self.status_file = Path(status_file)
        self._lock = threading.RLock()
        self.models: List[ModelConfig] = [self._coerce_model(m) for m in model_configs]
        self._load_status_from_disk()

    def _coerce_model(self, model: Dict[str, Any] | ModelConfig) -> ModelConfig:
        if isinstance(model, ModelConfig):
            return model
        return ModelConfig.from_dict(model)

    def _client(self, cfg: ModelConfig) -> OpenAI:
        return OpenAI(api_key=cfg.ark_api_key, base_url=self.base_url)

    def _load_status_from_disk(self) -> None:
        if not self.persist_status or not self.status_file.exists():
            return
        try:
            with self.status_file.open("r", encoding="utf-8") as f:
                stored = json.load(f)
        except Exception:
            return

        if not isinstance(stored, list):
            return

        stored_by_ep = {
            item.get("ep_id"): item
            for item in stored
            if isinstance(item, dict) and item.get("ep_id")
        }
        for model in self.models:
            item = stored_by_ep.get(model.ep_id)
            if item is not None and "usable" in item:
                model.usable = bool(item["usable"])

    def save_status(self) -> None:
        if not self.persist_status:
            return
        with self._lock:
            payload = [asdict(model) for model in self.models]
            tmp_path = self.status_file.with_suffix(self.status_file.suffix + ".tmp")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            tmp_path.replace(self.status_file)

    def reset_usable(self) -> None:
        with self._lock:
            for model in self.models:
                model.usable = True
        self.save_status()

    def _mark_unusable(self, idx: int) -> None:
        with self._lock:
            self.models[idx].usable = False
        self.save_status()

    @staticmethod
    def _error_info(err: Exception) -> tuple[Optional[int], str]:
        status_code = getattr(err, "status_code", None)
        message = str(err)
        return status_code, message

    @staticmethod
    def _is_quota_exhausted(status_code: Optional[int], message: str) -> bool:
        if status_code != 429:
            return False
        return "QuotaExceeded" in message and "free trial quota exhausted" in message

    @staticmethod
    def _is_rate_limited(status_code: Optional[int], message: str) -> bool:
        return status_code == 429 and "RateLimitExceeded" in message

    @staticmethod
    def _is_server_error(status_code: Optional[int]) -> bool:
        return status_code is not None and status_code >= 500

    def _iter_usable_models(self) -> Iterator[tuple[int, ModelConfig]]:
        for idx, model in enumerate(self.models):
            if model.usable:
                yield idx, model

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Any:
        last_error: Optional[Exception] = None
        for idx, cfg in self._iter_usable_models():
            client = self._client(cfg)
            try:
                resp = client.chat.completions.create(
                    model=cfg.ep_id,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                return resp
            except APIStatusError as err:
                last_error = err
                status_code, message = self._error_info(err)
                if self._is_quota_exhausted(status_code, message):
                    self._mark_unusable(idx)
                    continue
                if self._is_rate_limited(status_code, message):
                    try:
                        return client.chat.completions.create(
                            model=cfg.ep_id,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            **kwargs,
                        )
                    except Exception as retry_err:
                        last_error = retry_err
                        continue
                if self._is_server_error(status_code):
                    continue
                raise
            except Exception as err:
                last_error = err
                continue

        if last_error is not None:
            raise RuntimeError("All available models failed") from last_error
        raise RuntimeError("No usable models available")

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Iterator[str]:
        last_error: Optional[Exception] = None
        for idx, cfg in self._iter_usable_models():
            client = self._client(cfg)
            started = False
            try:
                stream = client.chat.completions.create(
                    model=cfg.ep_id,
                    messages=messages,
                    stream=True,
                    temperature=temperature,
                    **kwargs,
                )
                for chunk in stream:
                    text = self._extract_stream_text(chunk)
                    if text:
                        started = True
                        yield text
                return
            except APIStatusError as err:
                last_error = err
                status_code, message = self._error_info(err)
                if started:
                    raise RuntimeError(
                        f"Stream failed after partial output from {cfg.name}"
                    ) from err
                if self._is_quota_exhausted(status_code, message):
                    self._mark_unusable(idx)
                    continue
                if self._is_rate_limited(status_code, message):
                    continue
                if self._is_server_error(status_code):
                    continue
                raise
            except Exception as err:
                last_error = err
                if started:
                    raise RuntimeError(
                        f"Stream failed after partial output from {cfg.name}"
                    ) from err
                continue

        if last_error is not None:
            raise RuntimeError("All available models failed during streaming") from last_error
        raise RuntimeError("No usable models available")

    @staticmethod
    def _extract_stream_text(chunk: Any) -> str:
        try:
            choice = chunk.choices[0]
            delta = choice.delta
            return getattr(delta, "content", "") or ""
        except Exception:
            return ""


def load_models_from_json(path: str | os.PathLike[str]) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("model config file must contain a list")
    return data


def save_models_to_json(path: str | os.PathLike[str], model_list: Iterable[Dict[str, Any] | ModelConfig]) -> None:
    payload = [asdict(m) if isinstance(m, ModelConfig) else dict(m) for m in model_list]
    with Path(path).open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    models = [
        {
            "name": "Model A",
            "ep_id": "ep-xxxx1",
            "ark_api_key": "sk-xxxx",
            "usable": True,
        },
        {
            "name": "Model B",
            "ep_id": "ep-xxxx2",
            "ark_api_key": "sk-xxxx",
            "usable": True,
        },
    ]

    router = ArkModelRouter(models)
    result = router.chat([{"role": "user", "content": "Say hello in one sentence."}])
    print(result.choices[0].message.content)
