from __future__ import annotations

import json
import os
from pathlib import Path

from local_setup import MODELS
from router_client import RouterClientError

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "local_config.json"
MODEL_DIR = BASE_DIR / "models"


def load_settings(path: Path = CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            raise ValueError("not an object")
        return settings
    except (OSError, ValueError) as exc:
        raise RouterClientError("Local settings cannot be read. Re-run Setup_Jarvis to repair them.") from exc


def provider() -> str:
    value = os.getenv("JARVIS_PROVIDER") or load_settings().get("provider", "local")
    if value not in {"local", "router"}:
        raise RouterClientError("JARVIS_PROVIDER must be local or router.")
    return value


def local_model(settings: dict) -> str:
    model = settings.get("model")
    if model not in {choice.name for choice in MODELS}:
        raise RouterClientError("No supported local model is configured. Run Setup_Jarvis first.")
    return model


def save_settings(model: str, path: Path = CONFIG_PATH) -> None:
    choice = next(m for m in MODELS if m.name == model)
    content = {"provider": "local", "model": model, "whisper_model": choice.whisper}
    write_settings(content, path)


def write_settings(content: dict, path: Path = CONFIG_PATH) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
