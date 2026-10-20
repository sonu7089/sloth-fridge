from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "Sloth Fridge"


def _default_data_dir() -> Path:
    override = os.environ.get("SLOTH_FRIDGE_HOME")
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "SlothFridge"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "sloth-fridge"


def data_dir() -> Path:
    path = Path(os.environ.get("SLOTH_FRIDGE_HOME", _default_data_dir()))
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "sloth_fridge.db"


def photos_dir() -> Path:
    path = data_dir() / "photos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def inbox_dir() -> Path:
    path = data_dir() / "inbox"
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return data_dir() / "config.json"


def staples_path() -> Path:
    return data_dir() / "staples.json"


OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
VISION_MODEL = os.environ.get("SLOTH_VISION_MODEL", "qwen2.5vl:3b")
TEXT_MODEL = os.environ.get("SLOTH_TEXT_MODEL", "qwen2.5:3b")

MAX_IMAGE_EDGE = int(os.environ.get("SLOTH_MAX_IMAGE_EDGE", "1024"))
JPEG_QUALITY = int(os.environ.get("SLOTH_JPEG_QUALITY", "85"))
REQUEST_TIMEOUT = int(os.environ.get("SLOTH_TIMEOUT", "600"))

CATEGORIES = [
    "produce",
    "dairy",
    "meat",
    "seafood",
    "eggs",
    "bread",
    "frozen",
    "pantry_staple",
    "beverage",
    "condiment",
    "snack",
    "other",
]

CATEGORY_ORDER = [
    "produce",
    "meat",
    "seafood",
    "eggs",
    "dairy",
    "bread",
    "frozen",
    "pantry_staple",
    "beverage",
    "condiment",
    "snack",
    "other",
]

DEFAULT_STAPLES = [
    {"canonical": "milk", "name": "milk", "unit": "container", "threshold": 1, "buy_qty": 2, "category": "dairy"},
    {"canonical": "eggs", "name": "eggs", "unit": "piece", "threshold": 6, "buy_qty": 12, "category": "eggs"},
    {"canonical": "butter", "name": "butter", "unit": "pack", "threshold": 1, "buy_qty": 2, "category": "dairy"},
    {"canonical": "cheese", "name": "cheese", "unit": "pack", "threshold": 1, "buy_qty": 1, "category": "dairy"},
    {"canonical": "bread", "name": "bread", "unit": "loaf", "threshold": 1, "buy_qty": 1, "category": "bread"},
    {"canonical": "yogurt", "name": "yogurt", "unit": "container", "threshold": 1, "buy_qty": 2, "category": "dairy"},
    {"canonical": "chicken", "name": "chicken", "unit": "piece", "threshold": 1, "buy_qty": 1, "category": "meat"},
    {"canonical": "rice", "name": "rice", "unit": "container", "threshold": 1, "buy_qty": 1, "category": "pantry_staple"},
    {"canonical": "pasta", "name": "pasta", "unit": "pack", "threshold": 1, "buy_qty": 2, "category": "pantry_staple"},
    {"canonical": "olive oil", "name": "olive oil", "unit": "bottle", "threshold": 1, "buy_qty": 1, "category": "pantry_staple"},
    {"canonical": "coffee", "name": "coffee", "unit": "container", "threshold": 1, "buy_qty": 1, "category": "pantry_staple"},
]


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict) -> None:
    config_path().write_text(json.dumps(config, indent=2), encoding="utf-8")


def load_staples() -> list[dict]:
    path = staples_path()
    if not path.exists():
        return [dict(item) for item in DEFAULT_STAPLES]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return [dict(item) for item in DEFAULT_STAPLES]
    return data if isinstance(data, list) else [dict(item) for item in DEFAULT_STAPLES]


def save_staples(staples: list[dict]) -> None:
    staples_path().write_text(json.dumps(staples, indent=2), encoding="utf-8")
