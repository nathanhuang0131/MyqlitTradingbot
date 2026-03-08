Create qlib_tradingbot/docs/ARCHITECTURE.md describing:
- module layout and responsibilities (core, strategies, ml, llm, backtest, brokers)
- strategy execution lifecycle (scan → filter → score → risk → order → track → learn)
- artifact outputs under Artifacts/ (daily pack, model_scores, performance, feedback)
- safety design (paper default, live opt-in, kill switch)
- how model selector/evaluator works and how it improves over time

Keep it concise, practical, and aligned to the code.