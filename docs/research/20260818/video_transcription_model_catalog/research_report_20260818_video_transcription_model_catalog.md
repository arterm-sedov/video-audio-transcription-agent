# Video-transcription model catalog research report

Date: 2026-08-18  
Scope: Polza, OpenRouter, and direct Gemini model selection for Russian
speech-from-video transcription.  
Repository: `video-audio-transcription-agent`

## Executive summary

The research supports keeping the selector synchronous and multimodal. Polza's
public API documentation does not expose a Batch API or a `:batch` model mode;
its documented path is synchronous OpenAI-compatible Chat Completions. OpenRouter
does expose a Batch API, but its current documentation explicitly limits that
API to text-only requests. It therefore cannot be used as a cheap equivalent
for this video's audio track. OpenRouter Batch is asynchronous, targets a
24-hour completion window, and normally discounts token pricing by 50%; it is
not a streaming or latency-equivalent path.[1][2]

Gemini has a separate native Batch API with a 50% standard-cost discount and
asynchronous processing, but it is provider-specific and not evidence that a
Polza or OpenRouter `:batch` suffix supports video. Gemini's normal video/audio
documentation is the strongest general-purpose evidence for the Gemini family,
including transcription prompts with speakers, timestamps, and language
detection.[9][10][11]

For the current catalog, direct project probes provide the highest-confidence
Russian ranking: `minimax/minimax-m3` and `qwen/qwen3.6-plus` successfully heard
Russian speech in a meeting video and produced speaker-attributed dialogue.
`xiaomi/mimo-v2.5` remains a tested transport/model primer entry, but its
Russian transcription quality is unknown. Gemini entries are graded `good`
from documented multilingual audio/video capability rather than a local Russian
WER test. Other models are marked `unknown` unless there is reliable evidence
that they cannot hear video audio. A follow-up modality evidence pass closed the
remaining open entries: Z.AI's official model pages and Baidu's ERNIE-4.5-VL
model card confirm that `z-ai/glm-5v-turbo`, `z-ai/glm-5.1`, `z-ai/glm-5.2`,
and `baidu/ernie-4.5-vl-424b-a47b` cannot decode audio and video together, so
all four were excluded from the roster rather than left as unknowns.[25][26][27][28]

The catalog now excludes models with evidence of text-only, vision-only, or
audio-silent behavior, including MiniMax M2.7, Kimi K2.6/K3, the Qwen VL-only
families, Qwen candidates contradicted by the local audio probe, GLM-4.6V, and
Step-3.7-Flash, plus GLM-5V-Turbo, GLM-5.1, GLM-5.2, and ERNIE-4.5-VL.
These exclusions are deliberately narrower than name-based filtering: a direct
successful project probe keeps `qwen/qwen3.6-plus` despite generic platform
listings that do not fully describe its routed provider behavior.

## Introduction and research questions

The selector's purpose is not to list every vision-capable model. It must offer
models that can transcribe the audio track of a video, preserve the existing
provider fallback order, and remain useful for Russian meeting recordings. The
research answered five questions:

1. Does Polza expose a batch endpoint or `:batch` variant?
2. Does OpenRouter Batch provide an equivalent cheap path for video?
3. What quality and latency caveats apply to batch processing?
4. Which roster entries should be excluded as obsolete, text-only, vision-only,
   or unsuitable for speech-from-video?
5. Which surviving models have the best evidence for Russian transcription?

The web pass used current first-party documentation where available. It was
combined with the repository's live Polza probes, existing tests, and the
provider model metadata already used by the application.

## Findings

### 1. Polza batch support

Polza's canonical documentation index lists Chat Completions, Responses, audio
transcription and speech, models, storage, history, and balance APIs. It does
not list `batch`, `batches`, or a batch-processing endpoint.[3] The API
introduction describes Polza as OpenAI-compatible, but its generic HTTP status
description of `201` for asynchronous operations is not evidence of a public
batch inference contract.[4]

The documented multimodal inference route is `POST /api/v1/chat/completions`,
with `stream` as a request option.[6] The model documentation exposes modality
and pricing metadata, including `architecture.input_modalities` and audio,
speech-to-text, and video price fields.[5] This is useful for capability and
cost filtering, but neither document defines a batch mode.

Verdict: do not add a Polza `:batch` suffix or batch selector option. Keep
`:batch` in the generic variant-suffix filter until Polza publishes a specific
contract and the implementation has an asynchronous job lifecycle, result
polling, error retention, and tests.

The same documentation pass corrected a nearby transport detail. Polza's
official upload API names the multipart field `storagePolicy` and its documented
file cleanup route is `DELETE /api/v1/storage/files/{id}`.[7][8] The adapter now
uses those names. Temporary uploads still provide a safe fallback because the
documented temporary policy expires automatically.

### 2. OpenRouter Batch and multimodal equivalence

OpenRouter's Batch API accepts asynchronous request files and provides a target
completion window of 24 hours. Its quickstart currently states that the Batch
API is text-only: image, audio, video, and file content are rejected from the
batch request formats.[1] This is decisive for the current use case, even
though the normal OpenRouter API supports multimodal content when the selected
model explicitly accepts the relevant modality.[13]

OpenRouter documents Batch as typically 50% of standard per-token pricing, with
model-specific pricing as the source of truth. The result is returned after the
batch completes, associated with each request's `custom_id`; the workflow is
asynchronous and does not provide the interactive streaming semantics used by
the transcription orchestrator.[1]

The `flex` service tier should not be confused with Batch. Flex trades lower
cost for higher latency and capacity risk, but it is a service-tier routing
choice, not a multimodal batch endpoint.[12]

Verdict: do not route video chunks through OpenRouter Batch. The existing
`:batch` variant exclusion is correct for the selector, and the application
should continue using the synchronous multimodal request path. A future text
post-processing batch job could be separate, but it is outside this roster's
video capability contract.

### 3. Gemini Batch comparison

Gemini's native Batch API is real and documented. It processes GenerateContent
requests asynchronously at 50% of standard cost, with a target turnaround time
of 24 hours. Inputs may be inline below the documented size threshold or supplied
as a JSONL input file; the result is returned as inline responses or a JSONL
output file.[9]

Gemini's normal video documentation recommends the Files API for larger or
reused videos, and its audio documentation provides prompts for transcription,
speaker separation, timestamps, and language detection.[10][11] These are
strong reasons to keep direct Gemini in the catalog when it is reachable.

Batch is not quality-equivalent in operational terms: the underlying generation
contract is related, but completion is asynchronous, there is no interactive
streaming path, and the documented target is up to a day. The batch discount is
therefore a cost/latency tradeoff rather than a free replacement for the current
provider call.

### 4. Russian quality evidence

The strongest evidence is the repository's direct Polza probe report. On the
same Russian meeting capture, MiniMax M3 and Qwen3.6-Plus produced usable
speaker-attributed dialogue. Kimi K3 and GLM-4.6V behaved as vision-only
systems; Qwen3.8-Max and Step-3.7-Flash reported no audible audio.[24]

Qwen's general language documentation reports support for 119 languages and
dialects, including Russian, which is positive prior evidence for language
handling but does not by itself prove that every Qwen vision model consumes a
video audio track.[17] The Qwen visual API documentation explicitly says its
visual video models do not understand audio from video files.[16] Consequently,
the generic Qwen VL families are excluded, while the directly tested routed
`qwen/qwen3.6-plus` remains the strongest Qwen entry.

Xiaomi's official MiMo-V2.5 announcement describes native text, image, video,
and audio modalities.[18] That supports retaining MiMo-V2.5 as a candidate, but
there is no project Russian WER/probe result, so its catalog grade is `unknown`.
The Pro variant is excluded from this focused roster because the available
official description emphasizes agent and coding optimization rather than
speech-from-video evidence.[18]

Gemini's audio/video documentation supports transcription workflows and
language detection, so Gemini entries are graded `good`; this is documentation
evidence, not a local Russian benchmark. The remaining unprobed candidates were
checked explicitly against official modality documentation before being kept:
Z.AI's model pages were decisive for the GLM-5 family and Baidu's model card
for ERNIE; none accepted audio and video together, so none remains in the
roster as an unprobed unknown.[25][26][27][28]

### 5. Evidence-backed exclusions

The resulting exclusion policy is:

- `minimax/minimax-m2.7`: the official MiniMax page categorizes M2.7 among
  text-generation models, not an audio/video transcription model.[19]
- `moonshotai/kimi-k2.6`: Kimi's official quickstart lists text, image, and
  video, while Alibaba's model documentation explicitly says the video model
  does not process the audio track.[20][21]
- `moonshotai/kimi-k3`: local video probe was vision-only/no audible audio.
- `qwen/qwen2.5-vl-*` and `qwen/qwen3-vl-*`: Qwen's visual documentation says
  the video capability does not understand audio.[16]
- `qwen/qwen3.6-flash`, `qwen/qwen3.7-max`, `qwen/qwen3.8-max`: local probe or
  provider evidence does not establish audio-from-video transcription; the
  available direct probe for Qwen3.8-Max reported no audible audio.[24]
- `stepfun/step-3.7-flash`: local probe reported no audible audio.[24]
- `z-ai/glm-4.6v`: the official page documents visual video temporal reasoning,
  but the local probe found vision-only behavior and no speech transcription.[22][24]
- `z-ai/glm-5v-turbo`: Z.AI's official page lists input modalities Video /
  Image / Text / File with no audio, so it cannot hear a video's audio track.[25]
- `z-ai/glm-5.1` and `z-ai/glm-5.2`: Z.AI's official pages list Text input
  only; they are general/coding foundation models, not multimodal
  transcription candidates.[26][27]
- `baidu/ernie-4.5-vl-424b-a47b`: the official Baidu model card is tagged
  image-text-to-text and confirms the VL models focus on visual-language
  understanding, with no audio input.[28]
- `gemini-omni-video`: excluded as a generation/omni variant rather than a
  verified transcription candidate.

These are selector exclusions, not claims that a model can never transcribe
audio under any provider route. The catalog's purpose is a conservative default
for this application and can be revisited when a provider publishes a clearer
audio modality or a new direct probe succeeds.

## Synthesis and recommendations

The catalog should optimize for evidence before price. The implemented ordering
is now: tested models first; among those, stronger Russian evidence first; then
lower estimated input price; then stable model-id tie-breaking. This makes the
known-good Qwen and MiniMax entries visible before cheaper but unverified live
models, while retaining price as the final selection criterion.

Recommended default behavior:

1. Keep the current provider order `polza,openrouter,gemini`.
2. Keep live modality filtering and the static primer/exclusion union.
3. Keep `:batch` out of all video selectors for Polza and OpenRouter.
4. Use Polza hosted media when supported; otherwise use the existing inline
   fallback. The corrected storage field and delete route now match current
   Polza docs.
5. Treat `strong` as direct project evidence, `good` as first-party capability
   evidence, and `unknown` as an explicit invitation for future testing.
6. If a cheap asynchronous path is added later, expose it as a separate job
   mode with clear latency and non-streaming semantics, not as a model variant.

## Limitations

There is no public, comparable Russian WER benchmark for every model/provider
route in the unionized roster. Provider model IDs and capability metadata can
change without notice, and a provider's routed implementation may differ from
an upstream model card. The local probes are high-value evidence for the tested
models but are still a small sample: one meeting capture, one language, and
one application prompt. The Polza documentation index is strong negative
evidence against a public batch API, but it cannot rule out an undocumented or
private endpoint. The catalog therefore uses conservative exclusions and keeps
unknown entries visible when there is no direct failure evidence.

## Methodology appendix

Research was performed on 2026-08-18 using first-party documentation for Polza,
OpenRouter, Google Gemini, Qwen, Xiaomi, MiniMax, Kimi, and Z.AI. Search results
were used for discovery; claims were checked against the linked documentation
pages. The local evidence source was the repository's 2026-08-17 Polza storage
and Russian video probe report plus the current catalog and registry tests.

The persisted source ledger is [20_sources.md](20_sources.md). It records source
URL, access method, confidence, extracted evidence, and the decision supported
by each source. The 2026-08-18 follow-up modality pass added official Z.AI and
Baidu model pages as primary sources for the final four exclusions.

## Bibliography

[1] OpenRouter, “Batch API Quickstart,” https://openrouter.ai/docs/batch-quickstart  
[2] OpenRouter, “List all models,” https://openrouter.ai/docs/api/api-reference/models/get-models  
[3] Polza, “Documentation index,” https://polza.ai/docs/llms.txt  
[4] Polza, “API introduction,” https://polza.ai/docs/api-reference/introduction  
[5] Polza, “Models,” https://polza.ai/docs/gaidy/models  
[6] Polza, “Chat Completions,” https://polza.ai/docs/api-reference/chat/completions  
[7] Polza, “Upload file,” https://polza.ai/docs/api-reference/storage/upload  
[8] Polza, “Delete file,” https://polza.ai/docs/api-reference/storage/delete-file  
[9] Google, “Gemini Batch API,” https://ai.google.dev/gemini-api/docs/batch-api  
[10] Google, “Video understanding,” https://ai.google.dev/gemini-api/docs/video-understanding  
[11] Google, “Audio understanding,” https://ai.google.dev/gemini-api/docs/audio  
[12] OpenRouter, “Service tiers,” https://openrouter.ai/docs/guides/features/service-tiers  
[13] OpenRouter, “Multimodal overview,” https://openrouter.ai/docs/guides/overview/multimodal/overview  
[14] OpenRouter, “Models API,” https://openrouter.ai/docs/api/api-reference/models/get-models  
[15] Qwen, “API platform model capabilities,” https://qwen.ai/apiplatform  
[16] QwenCloud, “Vision,” https://docs.qwencloud.com/developer-guides/multimodal/vision  
[17] Qwen, “Qwen3,” https://qwenlm.github.io/blog/qwen3/  
[18] Xiaomi MiMo, “MiMo-V2.5 open sourced,” https://mimo.mi.com/docs/en-US/news/latest/v2.5-open-sourced  
[19] MiniMax, “Text generation,” https://platform.minimax.io/docs/guides/text-generation  
[20] Kimi, “Kimi K2.6 quickstart,” https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart  
[21] Alibaba Cloud, “Kimi API,” https://www.alibabacloud.com/help/en/model-studio/kimi-api  
[22] Z.AI, “GLM-4.6V,” https://docs.z.ai/guides/vlm/glm-4.6v  
[23] Project local catalog and tests, `src/transcription_agent/models_catalog.yaml` and `tests/test_model_registry.py`  
[24] Project local evidence, [Polza file storage and Russian video probe report](../Polza_File_Storage_URL_Upload_Deep_Research_20260817/research_report_20260817_polza_file_storage_url_upload.md)
[25] Z.AI, “GLM-5V-Turbo,” https://docs.z.ai/guides/vlm/glm-5v-turbo.md  
[26] Z.AI, “GLM-5.2,” https://docs.z.ai/guides/llm/glm-5.2.md  
[27] Z.AI, “GLM-5.1,” https://docs.z.ai/guides/llm/glm-5.1.md  
[28] Baidu, “ERNIE-4.5-VL-424B-A47B model card,” https://huggingface.co/baidu/ERNIE-4.5-VL-424B-A47B
