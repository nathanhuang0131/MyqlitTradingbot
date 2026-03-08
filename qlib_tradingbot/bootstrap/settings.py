from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ENV_SOURCE: Optional[Path] = None
_SETTINGS: Optional["BotSettings"] = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _resolve_env_path(project_root: Path | str | None = None) -> Optional[Path]:
    root = Path(project_root) if project_root else _project_root()
    candidate = root / ".env"
    if candidate.exists():
        return candidate
    return None


def bootstrap_environment(*, project_root: Path | str | None = None, force: bool = False) -> Optional[Path]:
    global _ENV_SOURCE, _SETTINGS
    env_path = _resolve_env_path(project_root)
    if env_path is None:
        if force:
            _ENV_SOURCE = None
            _SETTINGS = None
        return None
    if _ENV_SOURCE is None or force or _ENV_SOURCE != env_path:
        load_dotenv(dotenv_path=env_path, override=False)
        _ENV_SOURCE = env_path
        _SETTINGS = None
    return _ENV_SOURCE


@dataclass(frozen=True)
class BotSettings:
    api_key: str
    api_secret: str
    api_base_url: str
    paper: bool
    mode: str
    env_file: Optional[Path]


def _normalize_api_key() -> str:
    return str(os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY") or "").strip()


def _normalize_api_secret() -> str:
    return str(os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY") or "").strip()


def get_settings(*, refresh: bool = False) -> BotSettings:
    global _SETTINGS
    if refresh:
        _SETTINGS = None
    if _ENV_SOURCE is None:
        bootstrap_environment()
    if _SETTINGS is not None:
        return _SETTINGS
    paper = _as_bool(os.getenv("ALPACA_PAPER"), True)
    _SETTINGS = BotSettings(
        api_key=_normalize_api_key(),
        api_secret=_normalize_api_secret(),
        api_base_url=str(os.getenv("APCA_API_BASE_URL") or os.getenv("ALPACA_API_BASE_URL") or "").strip(),
        paper=paper,
        mode="paper" if paper else "live",
        env_file=_ENV_SOURCE,
    )
    return _SETTINGS


def is_broker_configured(settings: BotSettings | None = None) -> bool:
    cfg = settings or get_settings()
    return bool(cfg.api_key and cfg.api_secret)


def is_alpaca_available() -> bool:
    return importlib.util.find_spec("alpaca") is not None


def current_mode(settings: BotSettings | None = None) -> str:
    cfg = settings or get_settings()
    return cfg.mode


def env_source_path() -> Optional[Path]:
    bootstrap_environment()
    return _ENV_SOURCE


bootstrap_environment()
