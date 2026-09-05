**Time**: 2026-08-18, Europe/Moscow
**Source**: https://openrouter.ai/docs/batch-quickstart
**Method**: query-search and rendered documentation (web search/open)
**Confidence**: high
**Insight**: OpenRouter Batch API is real and asynchronous, with a 24-hour completion window and roughly 50% token pricing, but it is explicitly text-only for chat/responses/messages: image, audio, video, and file parts are rejected. It is therefore not a valid cheap path for this repository's video-transcription requests.

# Relevant extracted content

> “The Batch API lets you submit many inference requests together and retrieve the results asynchronously.”
>
> “The Batch API is currently text-only. On `/v1/chat/completions`, `/v1/responses`, and `/v1/messages`, validation rejects any request that carries image, audio, video, or file content parts.”
>
> “Batch requests are typically billed at 50% of the model’s standard per-token pricing.”
>
> Endpoint: `POST https://openrouter.ai/api/beta/batches`; poll with `GET https://openrouter.ai/api/beta/batches/:id`; only `24h` completion window.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://polza.ai/docs/gaidy/media-input
**Method**: rendered documentation (web open)
**Confidence**: high
**Insight**: Polza documents inline and hosted media input for images, documents, audio, and video. The media route is synchronous chat content, so it does not supply a batch equivalent.

# Relevant extracted content

> The guide is titled “Передача медиа на вход” and covers images, documents, audio, and video as input to models.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://polza.ai/docs/api-reference/storage/upload
**Method**: rendered documentation (web open/find)
**Confidence**: high
**Insight**: Polza has a documented storage upload endpoint suitable for the URL transport already validated by the project. The documented form uses `POST /api/v1/storage/upload` with multipart media and `storagePolicy=TEMP_UPLOAD`.

# Relevant extracted content

> `POST https://polza.ai/api/v1/storage/upload`
>
> The example sends multipart form data and `storagePolicy: TEMP_UPLOAD`.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://polza.ai/docs/api-reference/storage/delete-file
**Method**: rendered documentation (web open/find)
**Confidence**: high
**Insight**: The current Polza documentation identifies the delete route that the prior live-probe report had not found: `DELETE /api/v1/storage/files/{id}`. The adapter should use that route when it has a file id, while retaining best-effort cleanup semantics.

# Relevant extracted content

> `DELETE https://polza.ai/api/v1/storage/files/{id}`
>
> The documented response is `{ "success": true }`; deletion is irreversible.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://openrouter.ai/docs/guides/overview/multimodal/overview
**Method**: rendered documentation (web open/find)
**Confidence**: high
**Insight**: OpenRouter's multimodal contract distinguishes video-capable from audio-capable models, and uses `video_url` for video content. A model appearing in the video-capable list is not proof that it transcribes the audio track.

# Relevant extracted content

> “Not all models support every modality.”
>
> “Audio-capable models: Required for audio input processing” and “Video-capable models: Required for video input processing.”
>
> Video input uses `video_url`; local files use a `data:video/mp4;base64,...` data URL.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://openrouter.ai/docs/api/api-reference/models/get-models
**Method**: rendered documentation (web open/find)
**Confidence**: high
**Insight**: OpenRouter exposes `architecture.input_modalities` and related model metadata through `/api/v1/models`. The catalog filter can use these fields directly and should not infer audio/video support from a name when explicit metadata is present.

# Relevant extracted content

> Model objects include `architecture.input_modalities`, `architecture.modality`, and `architecture.output_modalities`.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://ai.google.dev/gemini-api/docs/video-understanding
**Method**: rendered documentation (web open/find)
**Confidence**: high
**Insight**: Gemini supports direct video understanding and recommends the Files API when requests exceed 20 MB, video is significant in duration, or a file is reused. This supports keeping Gemini models in the roster and using hosted file references.

# Relevant extracted content

> “Always use the Files API when the total request size ... is larger than 20 MB, the video duration is significant, or if you intend to use the same video in multiple prompts.”

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://ai.google.dev/gemini-api/docs/audio
**Method**: rendered documentation (web open/find)
**Confidence**: high
**Insight**: Gemini's current audio documentation gives a transcription workflow with speaker labels, timestamps, language detection, and video input examples. It is strong evidence for transcription suitability, though it does not constitute a Russian-specific WER benchmark for every Gemini variant.

# Relevant extracted content

> The example prompt requires distinct speakers, MM:SS timestamps, and primary-language detection.
>
> The interaction examples pass `type: "video"` and `type: "audio"`; Files API is recommended above 20 MB.
>
> Gemini documents 32 audio tokens per second and up to 9.5 hours of audio per prompt.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://qwen.ai/apiplatform
**Method**: query-search (web search)
**Confidence**: high
**Insight**: Qwen's current platform separates video-capable VLMs from audio/video-capable Qwen3-Omni and audio-only ASR. Qwen3.6-Plus is listed as text/image/video, not audio; the project’s tested qwen3.6-plus result is therefore important implementation-specific evidence rather than a generic family guarantee.

# Relevant extracted content

> Qwen3.6-Plus: “Inputs: Text,Image,Video.”
>
> Qwen3-Omni-Flash: “Inputs:Text,Image,Audio,Video.”

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://docs.qwencloud.com/developer-guides/multimodal/vision
**Method**: query-search (web search)
**Confidence**: high
**Insight**: QwenCloud explicitly states that Qwen3-VL and related visual models do not understand audio from video files. This is a hard exclusion signal for Qwen3-VL and Qwen2.5-VL entries in an audio-transcription selector, even though they accept video frames.

# Relevant extracted content

> “Audio understanding: The model does not support understanding the audio from video files.”
>
> The limitation is stated in the video-file input section covering Qwen3-VL and related visual models.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://qwenlm.github.io/blog/qwen3/
**Method**: rendered documentation (web open/find)
**Confidence**: medium-high
**Insight**: Qwen3's language-training coverage explicitly includes Russian among 119 languages and dialects. This supports a good Russian-language prior for Qwen-family text generation, but it does not override the separate audio-track limitation of the VL API family.

# Relevant extracted content

> “Qwen3 models are supporting 119 languages and dialects.”
>
> Russian is listed in the Indo-European language table.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://mimo.mi.com/docs/en-US/news/latest/v2.5-open-sourced
**Method**: query-search (web search)
**Confidence**: high
**Insight**: Xiaomi describes MiMo-V2.5 as a native full-modal model supporting text, image, video, and audio; MiMo-V2.5-Pro is positioned for coding and agent scenarios instead. This supports retaining the tested MiMo-V2.5 and removing the Pro variant from a video-transcription roster unless a provider separately documents its media input.

# Relevant extracted content

> “mimo-v2.5: A native full-modal model supporting text, image, video, and audio understanding.”
>
> The Pro model is described as optimized for complex Agent and Coding applications.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://platform.minimax.io/docs/guides/text-generation
**Method**: query-search (web search)
**Confidence**: high
**Insight**: MiniMax's M2.7 documentation classifies it as a text model for engineering, agents, and office work, so it is not a video-transcription candidate. This is separate from MiniMax M3, which the project directly verified as hearing Russian speech in video.

# Relevant extracted content

> “MiniMax text models” and the supported-model table includes MiniMax-M2.7.
>
> M2.7’s highlighted use cases are software engineering, agents, office delivery, and text generation.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart
**Method**: query-search (web search)
**Confidence**: high
**Insight**: Kimi K2.6 officially accepts text, image, and video, but the model-selection documentation does not claim audio-track understanding. A separate current model guide explicitly says it does not process the audio track in video files; exclude it for transcription.

# Relevant extracted content

> K2.6 “supports text, image, and video input.”

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://www.alibabacloud.com/help/en/model-studio/kimi-api
**Method**: query-search (web search)
**Confidence**: high
**Insight**: Alibaba Cloud’s current Kimi API documentation explicitly warns that Kimi does not process the audio track in video files. This corroborates the project’s Kimi K3 vision-only probe and justifies excluding both Kimi K3 and Kimi K2.6 from the transcription selector.

# Relevant extracted content

> “Audio understanding: The model does not process the audio track in video files.”

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://docs.z.ai/guides/vlm/glm-4.6v
**Method**: rendered documentation (web open/find)
**Confidence**: high
**Insight**: GLM-4.6V officially supports video/image/text/file input and strong visual video understanding, but public documentation does not establish speech recognition. The project’s direct Russian-video probe returned vision-only output, so GLM-4.6V remains excluded.

# Relevant extracted content

> “Input Modality: Video / Image / Text / File.”
>
> The documented video capability is visual temporal reasoning and summarization.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: `docs/research/Polza_File_Storage_URL_Upload_Deep_Research_20260817/research_report_20260817_polza_file_storage_url_upload.md`
**Method**: local primary-source live-probe report (project artifact)
**Confidence**: high for tested models and transport; medium for untested models
**Insight**: The project sent the same media through Polza as a stored URL and as inline base64, observed successful URL-based transcription, and measured lower prompt tokens/cost for the URL path. It also directly tested Russian speech from video: MiniMax M3 and Qwen3.6-Plus heard it; Kimi K3 and GLM-4.6V did not; Qwen3.8-Max and Step-3.7-Flash reported no audible audio; Gemini over OpenRouter was region-blocked.

# Relevant extracted content

> Stored Polza `video_url`: 13 prompt tokens and `0.0071` RUB versus inline base64: 781 prompt tokens and `0.0384` RUB for the same 10 KB clip.
>
> Full-file Russian speech probes produced speaker-attributed dialogue for `minimax/minimax-m3` and `qwen/qwen3.6-plus`; `moonshotai/kimi-k3` and `z-ai/glm-4.6v` were vision-only; `qwen/qwen3.8-max` and `stepfun/step-3.7-flash` reported no audible audio.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: `src/transcription_agent/models_catalog.yaml` and `tests/test_model_registry.py`
**Method**: local repository evidence
**Confidence**: high
**Insight**: The existing catalog already marks MiniMax M3, Qwen3.6-Plus, MiMo-V2.5, and Google Gemini 2.5 Flash as tested/primer entries, and already excludes Kimi K3 and GLM-4.6V. The research update extends this evidence-grounded approach rather than replacing it with name-only heuristics.

# Relevant extracted content

> `tested: true` is documented as verified speech-from-video evidence.
>
> `excluded: true` is documented as tested and unsuitable because of vision-only or audio-silent behavior.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://polza.ai/docs/llms.txt
**Method**: rendered documentation index (web open)
**Confidence**: high
**Insight**: Polza's canonical documentation index enumerates the public API surface. It includes synchronous chat completions, Responses, media generation/status/operations, audio transcription/speech, models, storage, history, and balance, but no batch/batches endpoint.

# Relevant extracted content

> “POST Chat Completions”, “POST Responses”, “POST Audio Transcriptions”, “GET Models”, storage operations, and “История генераций” are listed in the API reference.
>
> No `batch`, `batches`, or batch-processing endpoint appears in the complete index.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://polza.ai/docs/api-reference/introduction
**Method**: rendered documentation (web open)
**Confidence**: high
**Insight**: Polza documents its REST API as OpenAI-compatible and lists asynchronous operations only in the general HTTP status description; that does not establish a batch inference API. The documented file limit is 50 MB and the API timeout is 600 seconds.

# Relevant extracted content

> “Polza.ai предоставляет REST API, совместимый со стандартом OpenAI.”
>
> `201` is described as “Задача создана (для асинхронных операций)”; limits list a 50 MB maximum file size and 600-second timeout.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://polza.ai/docs/gaidy/models
**Method**: rendered documentation (web open)
**Confidence**: high
**Insight**: Polza exposes model type filtering including `audio` and `stt`, and model metadata exposes `architecture.input_modalities`, pricing fields, and operations. This supports capability filtering and price interpretation, but does not expose a batch mode.

# Relevant extracted content

> Model type values include `audio`, `video`, `tts`, and `stt`.
>
> `architecture.input_modalities` is an array; pricing may include `audio_per_million`, `stt_per_minute`, and `video_per_second`, with currency RUB.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://polza.ai/docs/api-reference/chat/completions
**Method**: rendered documentation (web open)
**Confidence**: high
**Insight**: Polza's documented multimodal inference path is synchronous Chat Completions at `/api/v1/chat/completions`, with `stream` available as a request option. This is the relevant route for video transcription and has no documented batch variant.

# Relevant extracted content

> `POST https://polza.ai/api/v1/chat/completions`
>
> The request schema includes `messages`, `stream`, `modalities`, and provider-routing options.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://ai.google.dev/gemini-api/docs/batch-api
**Method**: rendered documentation (web open)
**Confidence**: high
**Insight**: Gemini's native Batch API is asynchronous and discounted to 50%, but it is a separate Google API capability rather than a Polza/OpenRouter `:batch` suffix. It supports GenerateContent requests, including file-based JSONL input, with a 24-hour target and no implication of identical latency or streaming semantics.

# Relevant extracted content

> “The Gemini Batch API is designed to process large volumes of requests asynchronously at 50% of the standard cost.”
>
> “The target turnaround time is 24 hours.”
>
> Input may be inline under 20 MB or a JSONL file up to 2 GB; output is returned as inline responses or a JSONL file.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://openrouter.ai/docs/guides/features/service-tiers
**Method**: rendered documentation (web open)
**Confidence**: high
**Insight**: OpenRouter's current cost/latency controls are service tiers (`flex` and `priority`), distinct from the Batch API. Flex is lower cost/higher latency and restricted to flex endpoints; it is not a multimodal batch equivalent.

# Relevant extracted content

> “The `service_tier` parameter lets you control cost and latency tradeoffs.”
>
> `flex` is lower cost/higher latency; `priority` is faster/higher cost. Flex routes only to flex endpoints and can surface capacity errors.

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://docs.z.ai/guides/vlm/glm-5v-turbo.md
**Method**: first-party documentation (raw markdown)
**Confidence**: high
**Insight**: GLM-5V-Turbo is a multimodal coding foundation model; its official
page lists input modalities Video / Image / Text / File with no audio, so it
cannot hear a video's audio track and is excluded from the transcription roster.

# Relevant extracted content

> “Input Modality: Video / Image / Text / File”
>
> “GLM-5V-Turbo is Z.AI's first multimodal coding foundation model, built for
> vision-based coding tasks.”

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://docs.z.ai/guides/llm/glm-5.2.md
**Method**: first-party documentation (raw markdown)
**Confidence**: high
**Insight**: GLM-5.2 is a flagship text foundation model; its official page lists
Text input only, so it is not a multimodal transcription candidate.

# Relevant extracted content

> “Input Modalities: Text”
>
> “GLM-5.2 is a flagship model built for the era of long-horizon tasks.”

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://docs.z.ai/guides/llm/glm-5.1.md
**Method**: first-party documentation (raw markdown)
**Confidence**: high
**Insight**: GLM-5.1 is a flagship text foundation model; its official page lists
Text input only, so it is not a multimodal transcription candidate.

# Relevant extracted content

> “Input Modalities: Text”
>
> “GLM-5.1 is Z.AI's latest flagship model, designed for long-horizon tasks.”

---

**Time**: 2026-08-18, Europe/Moscow
**Source**: https://huggingface.co/baidu/ERNIE-4.5-VL-424B-A47B
**Method**: first-party model card (raw README)
**Confidence**: high
**Insight**: The ERNIE-4.5-VL-424B-A47B model card is tagged image-text-to-text;
the VLM focuses on visual-language understanding with no audio input, so it is
excluded from the transcription roster.

# Relevant extracted content

> `pipeline_tag: image-text-to-text`
>
> “The VLMs focuses on visual-language understanding and supports both thinking
> and non-thinking modes.”

---
