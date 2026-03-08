from __future__ import annotations

import importlib
from pathlib import Path


def _reload_settings():
    import qlib_tradingbot.bootstrap.settings as settings

    return importlib.reload(settings)


def test_settings_accepts_alpaca_alias_env(monkeypatch):
    for key in (
        "APCA_API_KEY_ID",
        "APCA_API_SECRET_KEY",
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("ALPACA_API_KEY", "alias-key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "alias-secret")
    monkeypatch.setenv("ALPACA_PAPER", "1")

    settings = _reload_settings()
    cfg = settings.get_settings(refresh=True)

    assert cfg.api_key == "alias-key"
    assert cfg.api_secret == "alias-secret"
    assert settings.is_broker_configured(cfg) is True
    assert settings.current_mode(cfg) == "paper"


def test_bootstrap_environment_reports_env_file(tmp_path: Path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("ALPACA_API_KEY=from-file\nALPACA_SECRET_KEY=from-file-secret\n", encoding="utf-8")

    for key in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)

    settings = _reload_settings()
    for key in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "ALPACA_API_KEY", "ALPACA_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    loaded = settings.bootstrap_environment(project_root=tmp_path, force=True)
    cfg = settings.get_settings(refresh=True)

    assert loaded == env_path
    assert cfg.env_file == env_path
    assert cfg.api_key == "from-file"
