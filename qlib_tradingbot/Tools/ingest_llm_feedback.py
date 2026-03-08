from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.LLM.feedback_handler import write_bias_state, parse_feedback_text


def _csv_to_strict_text(df: pd.DataFrame) -> str:
    """
    Convert the feedback_template.csv (filled by user) to the strict text format expected by parse_feedback_text.
    """
    # Column normalization
    cols = {c.lower().strip(): c for c in df.columns}
    sym_col = cols.get("symbol")
    bias_col = cols.get("bias")
    prob_col = cols.get("prob")
    action_col = cols.get("action")
    notes_col = cols.get("notes")

    if not sym_col:
        raise ValueError("CSV must contain a 'symbol' column.")

    lines: list[str] = []
    for _, row in df.iterrows():
        sym = str(row.get(sym_col, "")).strip().upper()
        if not sym:
            continue
        bias = str(row.get(bias_col, "Neutral") if bias_col else "Neutral").strip() or "Neutral"
        prob = str(row.get(prob_col, "0") if prob_col else "0").strip() or "0"
        action = str(row.get(action_col, "Hold") if action_col else "Hold").strip() or "Hold"
        notes = str(row.get(notes_col, "") if notes_col else "").strip()

        lines.append(f"SYMBOL: {sym}")
        lines.append(f"BIAS: {bias}")
        lines.append(f"PROB: {prob}")
        lines.append(f"ACTION: {action}")
        if notes:
            lines.append(f"NOTES: {notes}")
        lines.append("")  # blank line separator
    return "\n".join(lines).rstrip() + "\n"


def ingest_feedback_csv(*, input_csv: str | Path, out_dir: str | Path = "Data/llm_feedback") -> tuple[Path, Path]:
    input_csv = Path(input_csv)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv)
    text = _csv_to_strict_text(df)

    latest_txt = out_dir / "llm_feedback_latest.txt"
    state_json = out_dir / "llm_bias_state.json"

    latest_txt.write_text(text, encoding="utf-8")
    state = parse_feedback_text(text)
    write_bias_state(state_json, state)
    return latest_txt, state_json


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest LLM feedback CSV into bias state used for signal gating.")
    ap.add_argument("--input", required=True, help="Path to a filled feedback_template.csv.")
    ap.add_argument("--out-dir", default="Data/llm_feedback", help="Output folder (writes latest.txt + bias_state.json).")
    args = ap.parse_args()

    latest, state = ingest_feedback_csv(input_csv=args.input, out_dir=args.out_dir)
    print(f"[ingest_llm_feedback] wrote: {latest}")
    print(f"[ingest_llm_feedback] wrote: {state}")


if __name__ == "__main__":
    main()
