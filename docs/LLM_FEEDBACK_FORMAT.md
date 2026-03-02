# LLM Feedback Format

Input file: `Data/llm_feedback_latest.txt`

The parser expects repeated symbol blocks:

```
SYMBOL: AAPL
BIAS: Bullish
PROB: 72
ACTION: Hold

SYMBOL: TSLA
BIAS: Bearish
PROB: 64
ACTION: Trim
```

Allowed values:
- `BIAS`: `Bullish | Bearish | Neutral`
- `PROB`: `0-100`
- `ACTION`: `Hold | Trim | Exit | Add`

Output state file:
- `Data/llm_bias_state.json`

## Strategy Gating Rules
When state exists for a symbol:
- Bias conflicts with signal direction: skip signal
- Probability below threshold (`llm_prob_threshold`, default `60`): skip signal
- Neutral bias: reduce trade dollars by `llm_neutral_size_factor` (default `0.5`)

If no feedback state exists, behavior is unchanged.
