from __future__ import annotations


def test_diagnose_broker_setup_reports_structure():
    from qlib_tradingbot.Brokers import alpaca_clients

    report = alpaca_clients.diagnose_broker_setup(try_build=False)

    assert "env_file" in report
    assert "keys" in report
    assert "broker_configured" in report
    assert "alpaca_available" in report
    assert "client_build" in report


def test_masked_keys_are_not_plaintext(monkeypatch):
    from qlib_tradingbot.Brokers import alpaca_clients
    from qlib_tradingbot.bootstrap import settings as bootstrap_settings

    monkeypatch.setenv("APCA_API_KEY_ID", "ABCDEF123456")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "SECRET987654")
    bootstrap_settings.get_settings(refresh=True)

    report = alpaca_clients.diagnose_broker_setup(try_build=False)
    masked = report["keys"]
    assert masked["api_key"].startswith("AB")
    assert masked["api_key"] != "ABCDEF123456"
    assert masked["api_secret"] != "SECRET987654"

