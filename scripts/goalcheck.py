from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


CORE_FILES = [
    ROOT / "qlib_tradingbot/core/data_provider.py",
    ROOT / "qlib_tradingbot/core/features.py",
    ROOT / "qlib_tradingbot/core/qlib_signal_engine.py",
    ROOT / "qlib_tradingbot/core/portfolio_risk.py",
    ROOT / "qlib_tradingbot/core/execution_ledger.py",
]

CORE_IMPORTS = [
    "qlib_tradingbot.core.data_provider",
    "qlib_tradingbot.core.features",
    "qlib_tradingbot.core.qlib_signal_engine",
    "qlib_tradingbot.core.portfolio_risk",
    "qlib_tradingbot.core.execution_ledger",
]

DASH_IMPORTS = [
    "qlib_tradingbot.apps.dashboard_app",
    "qlib_tradingbot.dashboards.pages.1_Account",
    "qlib_tradingbot.dashboards.pages.2_Market",
    "qlib_tradingbot.dashboards.pages.3_FundFlows",
]

REQUIRED_SIGNAL_COLUMNS = ["symbol", "timestamp", "alpha", "direction", "confidence", "horizon", "model_id"]


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, out.strip()


def fail(msg: str) -> int:
    print(f"[goalcheck] FAIL: {msg}")
    return 1


def check_core_files() -> int:
    missing = [str(p.relative_to(ROOT)) for p in CORE_FILES if not p.exists()]
    if missing:
        return fail(f"missing core files: {missing}")
    print("[goalcheck] core files: ok")
    return 0


def check_imports(modules: list[str], label: str) -> int:
    for mod in modules:
        code, out = run([sys.executable, "-c", f"import importlib; importlib.import_module('{mod}')"])
        if code != 0:
            return fail(f"{label} import failed for {mod}\n{out}")
    print(f"[goalcheck] {label} imports: ok")
    return 0


def check_stub_signals() -> int:
    tmp = ROOT / "Data" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    sig = tmp / "signals.csv"
    if sig.exists():
        sig.unlink()

    code, out = run(
        [
            sys.executable,
            "-m",
            "qlib_tradingbot.core.qlib_signal_engine",
            "--stub",
            "--out",
            str(sig),
            "--symbols",
            "AAPL,MSFT,SPY",
        ]
    )
    if code != 0:
        return fail(f"stub signal engine run failed\n{out}")
    if not sig.exists():
        return fail("stub signal engine did not create signals.csv")

    with sig.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)
    if any(c not in cols for c in REQUIRED_SIGNAL_COLUMNS):
        return fail(f"signals.csv missing required columns: {REQUIRED_SIGNAL_COLUMNS}, got {cols}")
    if len(rows) == 0:
        return fail("signals.csv is empty")

    print("[goalcheck] stub signal engine output: ok")
    return 0


def check_perf_report() -> int:
    data_dir = ROOT / "Data" / "tmp_goalcheck_perf"
    out_dir = data_dir / "performance"
    data_dir.mkdir(parents=True, exist_ok=True)

    ledger = data_dir / "trades_ledger.csv"
    ledger.write_text(
        "timestamp,strategy,symbol,side,qty,fill_price,order_id,event,realized_pnl,fees,tags\n"
        "2026-03-01T00:00:00Z,goalcheck,AAPL,BUY,1,100.0,1,CLOSE,1.5,0.0,stub\n",
        encoding="utf-8",
    )

    code, out = run(
        [
            sys.executable,
            "-m",
            "qlib_tradingbot.Tools.perf_report",
            "--data-dir",
            str(data_dir),
            "--out-dir",
            str(out_dir),
        ]
    )
    if code != 0:
        return fail(f"perf_report failed\n{out}")
    pnl = out_dir / "pnl_daily.csv"
    wr = out_dir / "win_rate.csv"
    if not pnl.exists() or not wr.exists():
        return fail("perf_report did not generate pnl_daily.csv and win_rate.csv")

    print("[goalcheck] perf report outputs: ok")
    return 0


def main() -> int:
    checks = [
        check_core_files,
        lambda: check_imports(CORE_IMPORTS, "core"),
        check_stub_signals,
        check_perf_report,
        lambda: check_imports(DASH_IMPORTS, "dashboard"),
    ]
    for chk in checks:
        rc = chk()
        if rc != 0:
            return rc
    print("[goalcheck] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
