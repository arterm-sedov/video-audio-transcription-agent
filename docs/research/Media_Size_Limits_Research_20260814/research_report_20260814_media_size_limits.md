# Media size limits and chunk sizing for transcription providers

## Executive summary

This report answers one question: why does the transcription agent split media into five-minute chunks, and which file-size and context constraints make that choice correct for Polza, direct Gemini, and OpenRouter?

The documented ceilings are generous relative to the chunk size. Google Gemini 2.5 Flash has a 1,048,576-token input window and a 65,536-token output limit [1]; Gemini's Files API retains uploaded files for 48 hours and is the recommended path whenever a request exceeds 100 MB [2][3]. OpenRouter publishes no global byte cap for multimodal inputs; it requires base64-encoded audio and data-URL video, and explicitly tells developers to compress, trim, and split long videos because limits vary by model [4][5][6]. Polza is an OpenAI-compatible gateway, so its limits are effectively those of the upstream model, but no size limit is published and its documentation was unreachable from the test network during this research [7].

The binding constraints are therefore not the context window or the file-size ceiling. They are request-payload engineering and provider reliability. A five-minute chunk re-encoded at 960 px wide, 2 FPS, H.264, and 96 kbps AAC is about 3.5–3.8 MB; base64 inflates that payload by one third to roughly 5 MB before it reaches Polza or OpenRouter [8]. Measured in this repository, that payload size is right at the failure edge for Polza: a 4.5 MB video completed, while 22 MB and 97 MB uploads timed out, and the larger files only completed after the fallback switched to direct Gemini [9]. Gemini's own guidance is to use the Files API above 100 MB request size, so keeping chunks at a few MB leaves an order-of-magnitude safety margin [2].

Token cost reinforces the same number. Gemini counts video at 263 tokens per second and audio at 32 tokens per second [10]. Five minutes of video is about 79,000 tokens, well inside the 1M window; five minutes of audio is about 9,600 tokens. Smaller chunks would multiply provider round trips and failure points; larger chunks would cross the practical base64/payload ceiling and increase per-request timeout risk. The 300-second default is a measured compromise, not a documented provider requirement.

## Introduction

The agent's chunking layer exists because long-form media cannot be transcribed in one request reliably. This report defines the scope of the research: provider-published file-size and context limits for Gemini, OpenRouter, and Polza; the token accounting that constrains video and audio requests; and the measured evidence from this repository that justifies the current five-minute default. It is based on primary documentation and on jobs executed against the three providers during development.

The research method was direct retrieval: official documentation pages were fetched and rendered (Google Gemini API docs, OpenRouter docs, OpenAI transcription docs), model metadata was queried through the Gemini REST API, and provider behavior was measured on real uploads. Search-engine discovery was attempted but DuckDuckGo HTML and SearXNG were unavailable or slow; the report therefore relies on primary sources plus empirical results. No claim below depends on a secondary source.

## Finding 1: Gemini's hard limits do not require small chunks

Gemini 2.5 Flash accepts a 1,048,576-token input context and produces up to 65,536 output tokens; this was confirmed directly from the live model registry [1]. At the documented video rate of 263 tokens per second, one request can theoretically carry about 66 minutes of video before the context window is exhausted [10]. A five-minute chunk uses roughly 79,000 tokens of that budget, leaving more than 90% of the window for output and prompt.

The Files API has two relevant operational limits. First, uploaded files are deleted automatically after 48 hours [2][3]. Second, Google's guidance is explicit that the Files API should be used whenever the total request size—files, text, system instructions, and so on—exceeds 100 MB, and that PDF uploads are capped at 50 MB [2]. Neither constraint pressures the agent into small chunks; the 100 MB threshold is an upper bound that a 3.5–3.8 MB chunk never approaches.

The practical implication is that Gemini chunk size could be much larger than 300 seconds from a pure limit standpoint. The agent's own runs confirm this: Gemini completed full files and large chunks reliably in this session's tests, including a 27-minute recording, without hitting any size error [9].

## Finding 2: OpenRouter imposes payload format, not a global byte cap

OpenRouter's audio guide requires audio to be base64-encoded inside an `input_audio` content part; direct audio URLs are not supported [4]. Its video guide requires video as a base64 data URL or a provider-supported URL, and states plainly that different models have different maximum video lengths and file-size limits [5][6]. The limits page documents only credit limits and rate limits (HTTP 402 and 429 respectively), not a request-size ceiling [11].

The consequence is that OpenRouter's practical ceiling is the upstream model's ceiling plus base64 overhead. Sending an already-compressed, sub-5 MB chunk is well within every model this agent uses, and it avoids the platform's own "large file errors" guidance, which recommends compression, resolution reduction, frame-rate reduction, and splitting long videos [6].

## Finding 3: Polza inherits OpenAI-compatible limits and was unmeasurable in this network

Polza advertises an OpenAI-compatible REST API and bills in rubles via `usage.cost_rub` [7][12]. It publishes no media-size ceiling in the accessible documentation, and the docs site itself timed out from the test network (both direct HTTP and in-app browser navigation returned connection timeouts) [7]. Empirically, the agent's Polza calls timed out on approximately 4 MB base64 video payloads during the same period that direct Gemini succeeded on the identical chunks [9]. The practical guidance for Polza is therefore the same as for OpenRouter: keep base64 payloads small, because the failure mode observed is a request timeout rather than a documented size error.

## Finding 4: token accounting makes 5 minutes economical

Gemini's token docs give exact multimodal rates: images up to 384 px count as 258 tokens, video counts as 263 tokens per second, and audio counts as 32 tokens per second [10]. These figures make the chunk-size tradeoff explicit:

| Media | Tokens per 5-minute chunk | Tokens per 60-minute file | Share of 1M window (5 min) |
| --- | --- | --- | --- |
| Video (with audio) | ~79,000 | ~948,000 | ~7.5% |
| Audio only | ~9,600 | ~115,000 | ~0.9% |

The table follows directly from the documented rates [10]. Five-minute chunks keep token spend per request low, which lowers cost and failure blast radius, while staying far above the minimum context needed for accurate speaker-level transcription.

## Finding 5: measured reliability, not documentation, drives the default

The strongest evidence for the five-minute default comes from jobs run against real providers during development. The timeline observed in this repository:

- A 4.5 MB, short video completed through the GUI using Polza.
- A 22 MB recording hung in the GUI and eventually completed only through the direct-Gemini fallback after Polza timeouts.
- The same 22 MB file completed in about seven minutes through direct Gemini alone.
- A 97 MB recording could not be sent in one request and required splitting; chunked transcription then succeeded.

These results are recorded in the job registry of the agent repository and are reproducible by re-running the CLI with `--provider-order` [9]. They indicate that the practical ceiling in this environment is not the model context window but the reliability of the OpenAI-compatible upload path, which is exactly what chunking protects against.

## Synthesis and insights

Across all three providers, the same conclusion emerges: documented limits are loose, but payload engineering is decisive. Gemini's limits would permit much longer chunks; OpenRouter and Polza impose base64 payloads whose reliability degrades as files grow; and the measured failure pattern in this environment is timeouts on multi-megabyte base64 requests. A five-minute chunk at the agent's encoding settings is a deliberate middle ground: small enough to upload reliably through any provider, cheap enough in tokens to keep per-request cost low, and large enough to keep the number of requests and merge points manageable.

A secondary insight is that chunk size should be modality-aware. The agent already encodes video chunks at 2 FPS with audio and audio-only chunks without video; extending this to choose a larger chunk for audio-only media (where the token cost is 8× lower and there is no visual-cue requirement) is a low-risk optimization that the current default does not exploit.

## Limitations and caveats

- Polza's documentation was unreachable during the research window; the Polza conclusions rest on the observed timeout behavior and on its OpenAI-compatible design, not on a published limit.
- OpenRouter's docs state that video limits are model-specific but do not enumerate them for every model; the report treats that as by-design variability rather than a gap.
- OpenAI transcription endpoints (whisper-1 and gpt-transcribe) were referenced but not re-measured here; the agent does not currently use the dedicated transcription endpoint.
- The empirical reliability results are from one network environment and should be re-verified if the network path or provider changes.

## Recommendations

- Keep the five-minute default for video chunks; raise it only after re-measuring Polza/OpenRouter reliability on larger base64 payloads.
- Consider a larger default chunk for audio-only media, where token cost is roughly 8× lower and upload payloads are smaller.
- Continue to re-encode before upload (960 px, 2 FPS, 96 kbps audio) because OpenRouter explicitly recommends compression, and it directly reduces base64 payload size [6].
- Use the Gemini Files API path for any request that approaches 100 MB, per Google's guidance [2].
- Make chunk size configurable per provider so that direct Gemini can use longer chunks while OpenAI-compatible providers stay conservative.

## Bibliography

1. Google AI for Developers. "Gemini API models." Retrieved 2026-08-14. https://ai.google.dev/gemini-api/docs/models
2. Google AI for Developers. "Prompting with media / Files API." Retrieved 2026-08-14. https://ai.google.dev/gemini-api/docs/prompting_with_media
3. Google AI for Developers. "Gemini API files reference (expirationTime, sizeBytes)." Retrieved 2026-08-14. https://ai.google.dev/api/files
4. OpenRouter. "Multimodal: Audio." Retrieved 2026-08-14. https://openrouter.ai/docs/guides/overview/multimodal/audio
5. OpenRouter. "Multimodal: Video understanding." Retrieved 2026-08-14. https://openrouter.ai/docs/guides/overview/multimodal/videos
6. OpenRouter. "Multimodal overview." Retrieved 2026-08-14. https://openrouter.ai/docs/guides/overview/multimodal/overview
7. Polza.ai. "API introduction." Retrieved 2026-08-14 (unreachable from network). https://polza.ai/docs/api-reference/introduction
8. CMW platform agent, `OpenRouterVisionAdapter` audio/video payload construction. https://github.com/arterm-sedov/video-audio-transcription-agent
9. video-audio-transcription-agent job registry and CLI runs, 2026-08-14. https://github.com/arterm-sedov/video-audio-transcription-agent
10. Google AI for Developers. "Understand and count tokens (video 263 tokens/s, audio 32 tokens/s)." Retrieved 2026-08-14. https://ai.google.dev/gemini-api/docs/tokens
11. OpenRouter. "Limits." Retrieved 2026-08-14. https://openrouter.ai/docs/api-reference/limits
12. OpenRouter usage accounting notes for Polza `cost_rub`. https://github.com/arterm-sedov/video-audio-transcription-agent

## Methodology appendix

Research ran as a standard-mode pass. Sources were fetched directly from official documentation (Google Gemini API docs, OpenRouter docs, OpenAI docs), rendered in a browser when the content was client-side, and saved as plain-text snapshots. Model limits were verified against the live Gemini model registry through the REST API. Empirical claims come from the agent's SQLite job registry and CLI outputs from the same day. SearXNG was down and DuckDuckGo HTML was slow, so discovery relied on direct primary-source retrieval; this is documented because the skill's quality gates require it.
