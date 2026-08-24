# Model roster

Model-level ratings are shared across Polza, OpenRouter, and Gemini. Selectors sort **tested speech-from-video first**, then **quality, price, speed**. Reliability is documented, not a sort key. Do not re-probe Qwen, MiniMax, Claude, Muse, or GPT unless Polza advertises audio+video on those ids.

| model | quality | price | speed | reliability | note |
|---|---|---:|---|---|---|
| google/gemini-3.1-flash-lite | strong | 0.05 | fast (13.1s) | high | default; named speakers on 5 min |
| google/gemini-3.5-flash-lite | strong | 0.05 | fast (25.7s) | high | strong, slightly slower |
| google/gemini-3.6-flash | strong | 0.10 | medium (44s) | high | keep |
| google/gemini-3.7-flash | strong | 0.15 | fast (26.1s) | high | keep |
| google/gemini-2.5-flash | strong | 0.30 | fast (25.8s) | mixed | cheapest 5-min job ($0.0034); SOCKS flake |
| google/gemini-3.5-flash | strong | 0.30 | medium (43s) | high | keep |
| google/gemini-2.5-pro | strong | 1.25 | slow (114s) | high | over-segmented, expensive |
| google/gemini-2.5-flash-lite | good | 0.05 | slow (123s) | low | 5-min hallucinated 3453 "Да." lines |
| xiaomi/mimo-v2.5 | good | 0.14 | medium (86s) | mixed | gold at 60s, empty speech at 5 min |

## Cost reporting

Costs are reported per run in USD. Polza reports `cost_rub` (rubles), which is authoritative and converted via `POLZA_RUB_TO_USD_RATE` (default 90); never treat it as USD. OpenRouter reports `cost` in USD. Direct Gemini does not return a comparable cost in the API response, so its spending is only visible on the Gemini dashboard.

Excluded: Qwen 3.6/3.7 and MiniMax M3 (video, no audio), Claude/GPT (400 no video endpoints), Muse Spark (OpenRouter 18+ gate).
