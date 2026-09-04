Transcribe every spoken word in this video clip. The clip covers original-video time {start} through {end}.

Completeness is mandatory: every audible word by every speaker must appear; omitting a word or speaker turn is a failure. Do not summarize, compress, clean up, paraphrase, or silently skip filler words, repetitions, false starts, short acknowledgements, interruptions, or overlapping speech. Use [inaudible] only for a genuinely unintelligible word, never as a shortcut.

Treat word-for-word transcription and speaker attribution as separate checks: uncertainty about a name must never cause speech to be omitted, shortened, or paraphrased. Process the clip in sequential temporal portions and inspect more than one current frame when possible, especially at the start of speech and after a layout change.

Inspect the audio and the current video layout in every temporal portion of the clip. Participants may join, leave, move between tiles, or start/stop screen sharing. Screen sharing changes the visible layout, not the audio: continue transcribing every word while a screen or application is shown, including the presenter and other participants. Rebuild the visible-name mapping whenever the layout changes. Keep a displayed name consistent within the clip and across chunks when the same participant reappears, but do not force an old mapping when current visual evidence conflicts. Use every explicit platform cue that identifies the current speaker—regardless of color, brightness, contrast, shape, size, or position. This includes a green or differently colored active-speaker frame, a dark or light highlight, outline, focus box, changed tile background, avatar illumination or ring, speaking indicator, label, or an equivalent marker at the left, right, top, bottom, center, around an avatar, or around the tile. A status icon or badge is not automatically irrelevant: follow its actual meaning in that layout, and reject it only when it is demonstrably unrelated to speaker activity. The displayed name on the identified active tile is the strongest identity evidence; use voice only as a secondary cue. If evidence remains ambiguous, use SpeakerN rather than guessing. Match speaker-name language to the transcript: when the conversation is entirely Russian and the visual cue gives a Russian name, keep that name in Russian; otherwise render the name in the transcript language when a standard form is clear, without inventing a translation.

When screen sharing moves participant tiles to a sidebar or another compact layout, identify the current participant selected by the active cue there, regardless of its color, shape, contrast, or location; never carry a tile position forward from the previous layout and never mistake text or a person shown inside the shared application for the speaker. Copy a legible displayed name in its displayed script, without invented spellings, phonetic guesses, or unrelated company/UI text. If only a partial or conflicting name is visible, use SpeakerN until stronger visual evidence resolves it.

Visual checkpoints and candidate events are supplementary evidence. A checkpoint
label such as `[original-video time 00:22:14.000]` refers to the original media
timeline; transcript timestamps still follow the requested clip-relative format.
Inspect the attached still at that exact time and compare it with nearby
checkpoints. Use frames before, at, and after a candidate event to determine
whether the layout, participant membership, tile location, screen sharing, or
active-speaker cue changed. FFmpeg scene-change timestamps are candidates only:
they do not prove a speaker change, and a subtle active cue may change without
triggering scene detection. Never use a candidate event to discard audio,
create a silence marker, or move a transcript timestamp without checking the
actual video and audio. When a layout changes, rebuild the speaker mapping
from the current frame, including a sidebar or compact strip, and use every
explicit cue regardless of color, shape, contrast, or position. Keep the
video/audio pass lossless even when the still image is ambiguous.

Speaker-name normalization is mandatory before the final transcript. Treat every name produced during the audio pass as a candidate alias, not as ground truth. For each candidate, inspect frames at its turns and nearby moments, using the current active-speaker cue and visible tile name to resolve aliases. When frames establish that variants such as phonetic misspellings, OCR errors, clipped names, or company-suffixed labels refer to one participant, replace them with one canonical displayed name consistently across the whole clip and all chunks. Do not retain several spellings for the same visually identified person. If frames do not establish the identity or exact spelling, use SpeakerN rather than selecting the most plausible name. This pass changes speaker labels only and must never change, shorten, or paraphrase the spoken words.

If a later request explicitly says `LABEL_ONLY_NORMALIZATION`, do not
transcribe or rewrite the supplied speech. Inspect only the supplied checkpoint
images and label occurrences, and return the requested JSON mapping. Map a
variant only when the current visual evidence clearly identifies it as the same
participant; otherwise return an empty mapping. This mode may change labels only
and must never change words, timestamps, segment count, or ordering.

Output requirements:
- Return only a chronological transcript.
- Put EXACTLY ONE speaker turn per line, with a hard newline between every turn.
- Use exactly this line format: [MM:SS] Speaker: words
- Never concatenate multiple turns onto one line or embed a new timestamp inside speech.
- Timestamps are relative to this clip; do not use hours.
- Preserve words as spoken, including fillers, repetitions, false starts, interruptions, and overlap.
- Before responding, perform a completeness pass over the whole clip and verify that no audible speech was omitted.
- Check that no long line contains additional embedded timestamp/name markers; split every such marker into its own turn before responding, without dropping the speech between markers.
- Complete the frame-based speaker-name normalization pass before returning the transcript.
- Do not add a speaker key or commentary.
