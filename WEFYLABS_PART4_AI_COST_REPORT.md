# WefyLabs Part 4 — AI Cost Report

| Measure | Observed value |
|---|---|
| Provider/model | Configurable Google Gemini adapter; model name from `GEMINI_MODEL` |
| Average input tokens | NOT MEASURED |
| Average output tokens | NOT MEASURED |
| Average tool calls | NOT MEASURED |
| Context construction cost | NOT MEASURED |
| Simple-query cost | NOT MEASURED |
| Property-search cost | NOT MEASURED |
| Multi-step cost | NOT MEASURED |
| Fallback usage | NOT MEASURED |

The runtime persists per-turn provider, model, prompt tokens, completion tokens, total tokens, latency, and reported cost in `LLMUsage`. No price is asserted in this report because no production usage sample was supplied. Token controls presently include bounded recent turns, summary-plus-memory context, output token limits, a low-token qualification extraction pass, and a provider circuit breaker.
