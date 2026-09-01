# Bangla Subtitle Studio V3.4.0 Human Emotion Text To Voice

## V3.4.0 human emotion voice

- Natural, Happy, Loving, Angry, Sad, Serious and Storytelling delivery presets.
- Emotion Strength, sentence-aware breathing pauses, Speed and Pitch controls.
- Short Voice Preview before generating the complete MP3.
- The UI identifies Microsoft Natural Voice and explicitly warns when the more robotic Google Basic fallback was required.
- Basic fallback is disabled by default so a connection failure cannot silently produce a robotic final voice; it remains available through an explicit checkbox.
- Bengali, English, Hindi, Arabic and Urdu Text To Voice remain API-key-free and have no per-voice charge; internet is required.

## V3.3.0 highlights

- New Text To Voice tab with Bengali, English, Hindi, Arabic and Urdu.
- Natural Voice ID selection, Slow/Fast speed and low/high pitch controls.
- Long scripts are generated in reliable chunks and joined into one MP3.
- Avro/Banglish is strict ASCII Roman-only, with no Bengali vowel/hasanta marks.
- No API key or per-voice charge; natural voice requires internet.


## V3.3.0 resilient offline sentence recovery

- Does not cancel an entire video because one offline sentence candidate uses the wrong alphabet.
- Tries another meaning-preserving candidate, retries the sentence, then uses an offline English bridge.
- Accepts Roman person/brand names inside a real Bengali sentence.
- Keeps a difficult final phrase audible instead of leaving a silent gap.

## V3.3.0 natural Bengali and timing fix

- Common literal Hindi fallback such as `আপনি কিভাবে? আমি ঠিক আছে।` is normalized to natural spoken Bengali: `আপনি কেমন আছেন? আমি ঠিক আছি।`.

## V3.2 complete phrase and timing fix

- Hindi-to-Bengali dubbing is split into short phrases of at most 10 source words or 5.5 seconds instead of reconnecting speech into 12-second blocks.
- A translated phrase is never slowed unnaturally and its final words are never trimmed; a longer phrase is fitted completely before the next phrase starts.
- Natural source pauses remain silent without stretching the preceding Bengali voice across the pause.
- Generic Whisper prompt text was removed from multilingual recognition so it cannot be repeated or confused with the real Hindi speech.
- Mixed Hindi/Bengali/English alphabet output is rejected before speech generation.
- The packaged test now requires multiple short phrases, Hindi-to-Bengali meaning, no missing audio and no internal silence longer than 2.2 seconds in a continuous sample.

## V3.1 accuracy and speed update

- Bengali-to-English, English-to-Bengali, Bengali-to-Hindi, Hindi-to-Bengali, Hindi-to-English, and English-to-Hindi Voice Translate use sentence-level Google translation first.
- Every online result is checked for the target writing system; invalid text is rejected automatically.
- Subtitle sentences are sent in small bounded Google batches so distant lines cannot be merged or reordered; the bundled meaning-checked Offline M2M100 model is the automatic fallback.
- Non-Bengali source recognition is upgraded from Whisper Small to verified Whisper Large V3 Turbo Q5_0 for more faithful Hindi and English speech-to-text.
- Adjacent voice fragments are joined into complete sentences before translation, preserving context.
- Online translation avoids loading the large Offline translation model in the normal path, making the 34–56% stage much faster.

Windows desktop software for creating timed subtitles, translating spoken audio into a new natural-language voice, editing subtitle style, placing a logo, adjusting video color, and exporting a new MP4.

## V3.0.1 connection fix

- If Microsoft Edge natural voice cannot connect, the software automatically switches to Google Text-to-Speech.
- The fallback covers Bengali, Hindi, English, Arabic, Urdu and other supported Google voice languages without an API key or per-video charge.
- If Edge voice synthesis fails after a voice was selected, each sentence is retried through Google automatically.
- Google fallback uses its default voice; the male/female preference applies when the primary Microsoft voice is available.
- The packaged application must create real Bengali fallback audio before the installer is released.

## Voice Translate introduced in V3.0

- Adds a separate Multilanguage Voice Translate / Dubbing tab.
- Source and target voice languages are selected independently: Bengali, English, Hindi, Arabic, Urdu and the other existing languages are available.
- Examples include Hindi voice to Bengali voice, Bengali voice to English/Hindi/Arabic voice, Arabic voice to Bengali voice, and English voice to Bengali voice.
- A verified multilingual Whisper Small Q5_1 model recognizes non-Bengali source speech locally.
- M2M100 performs source-to-target translation locally and back-translates candidates to protect meaning.
- Natural male or female target speech is generated online without an API key and fitted sentence-by-sentence to the original timing and pauses.
- Original audio volume is adjustable from 0% to 30%; 0% fully replaces the original spoken audio.
- Translated text can automatically remain as timed subtitles for styling and final export.
- The packaged Windows app must pass a complete Hindi-voice-to-Bengali-voice video test before release.

## Subtitle improvements retained from V2.6

- Avro/Banglish now contains Roman letters only; Bengali is no longer repeated underneath it.
- Every Avro and English word starts with a capital letter, for example `Bismillahir Rahmanir Rahim`.
- A Global Sync controller moves the complete current subtitle earlier or later without regenerating it or selecting a language again.
- Short adjacent speech fragments are joined into a complete sentence instead of leaving `কেমন আছেন` alone on the next cue.
- The native ASR line limit is increased to 84 characters, and the default final display line limit is 70 characters.
- The Bismillah opening phrase receives a comma before a continuing sentence.

## Accuracy retained from V2.5

- Restores the proven V2.2 Bengali Whisper Medium Q4 model for faithful speech-to-text.
- Adds Silero Voice Activity Detection so real speech is found from its correct position and music/silence causes fewer hallucinations.
- Uses native timed cues and sentence-aware joining instead of estimating the timing of arbitrary word pieces.
- Generates two target-language candidates and back-translates both to Bengali, then keeps the candidate closest to the original meaning.
- Preserves common Islamic greetings such as Assalamu Alaikum when translating.
- Keeps the tolerant SRT reader introduced in V2.4.1.

## Features

- Offline subtitles need no OpenAI API key, billing, account, or Internet connection; Voice Translate needs Internet for Microsoft or Google speech.
- Transcription runs locally with `whisper.cpp` and a dedicated Bengali fine-tuned Whisper Medium Q4 model.
- Accurate Bengali (`bn`) speech recognition remains permanently selected for the source audio.
- Subtitle output can be Bengali Unicode, Avro/Banglish, Hindi, English, Arabic, Urdu, Nepali, Punjabi, Tamil, Telugu, Gujarati, Persian, Spanish, French, German, Italian, Portuguese, Russian, Turkish, Chinese, Japanese, or Korean.
- A bundled CTranslate2 INT8 M2M100 model performs translation locally without an API key.
- Avro/Banglish output is generated by the bundled `avro.py` reverse transliterator as a Roman-only line.
- Subtitles are shifted 0.35 seconds earlier by default to improve voice sync; this value is adjustable in the Subtitle tab.
- After generation, the Global Sync buttons move every current subtitle earlier or later in one click, regardless of its language.
- Live percentage and elapsed time are shown while the subtitle is generated, even between model progress updates.
- The AI engine and model are included in the Windows installer.
- Existing subtitle editing, SRT, logo, color, project, preview, and export features remain available.

The installer contains the more accurate 424 MB Bengali speech model, a multilingual source-speech model, a small VAD model, and the multilingual translation model. Bengali Unicode and Avro output are fastest because they do not need neural translation. Other target languages take longer because the software checks meaning by back-translation. Processing speed depends on the computer's CPU. Video and extracted audio remain on the computer; Voice Translate sends only the already translated text to the online natural-voice service.

## Download

Download `Bangla_Subtitle_Studio_Human_Emotion_Voice_Setup_V3.4.0.exe` from the `v3.4.0` GitHub Release and install it normally. Earlier installations can be upgraded because the installer keeps the same application identity.

## Developer build

The GitHub Actions workflow builds and bundles:

- Python runtime and the application
- FFmpeg, FFprobe, and FFplay
- statically built `whisper.cpp` CLI
- verified `ggml-bengali-medium-q4_0.bin` Bengali fine-tuned model
- verified `ggml-large-v3-turbo-q5_0.bin` multilingual source-speech model
- verified Silero V6.2 Voice Activity Detection model
- bundled INT8 M2M100 translation model covering 100 languages
- bundled Avro/Banglish reverse transliteration
- real Bengali speech test that must produce Bengali Unicode text and a readable timed SRT
- packaged Bengali greeting-to-Hindi and English semantic translation tests
- packaged six-direction Bengali/English/Hindi accurate translation test
- packaged real Google Bengali fallback-audio test
- packaged full Hindi-voice-to-Bengali-voice video test using an online natural target voice
- Inno Setup installer and SHA-256 checksum

Complete Bangla usage instructions: [README_BN.md](README_BN.md)

Third-party notices: [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)
