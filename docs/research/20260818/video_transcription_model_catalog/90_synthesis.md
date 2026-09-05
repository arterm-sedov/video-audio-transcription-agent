# Research synthesis

The provider research is conclusive for the current implementation boundary:

- Polza has no documented public batch endpoint or `:batch` contract. Its
  multimodal path is synchronous Chat Completions.
- OpenRouter Batch is asynchronous, usually 50% token pricing, and currently
  text-only. It cannot replace a video transcription request.
- Gemini Batch is a real asynchronous 50%-priced API, but it is provider-native
  and operationally distinct from the synchronous path.
- Russian priority should be `minimax/minimax-m3` and `qwen/qwen3.6-plus`
  (direct project evidence), followed by documented Gemini candidates, then
  unverified candidates. MiMo-V2.5 remains a tested primer entry but is not
  Russian-graded.
- Vision-only, text-only, and locally audio-silent models are excluded from the
  selector. The detailed rationale and bibliography are in the final report.

Implementation consequences: tested models sort first, Russian-quality metadata
breaks ties before price, and Polza storage now follows its documented
`storagePolicy` upload field and `/storage/files/{id}` deletion route.

Live discovery hardening (after the 2026-08-18 live probe): the selector no
longer guesses from model-id keywords. Live candidates must explicitly list
both `audio` and `video` input modalities; `:free`/`-free` tiers and
`openrouter/auto` routing ids are filtered as variants; and the curated catalog
is the stable floor in every mode. This keeps the CLI/GUI selectors dry across
network states: the tested primer is always first, curated entries follow, and
only genuinely audio+video-capable discoveries are appended.

Final evidence pass (same day): Z.AI's official model pages and Baidu's
ERNIE-4.5-VL model card confirm the four remaining unknowns cannot decode audio
and video together (GLM-5V-Turbo: Video/Image/Text/File, no audio; GLM-5.1 and
GLM-5.2: Text only; ERNIE-4.5-VL: image-text-to-text). All four are excluded, so
the roster contains no unprobed unknowns — every entry either has direct
project evidence or documented audio+video input.
