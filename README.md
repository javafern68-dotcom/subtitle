# Bangla Subtitle Studio V2 Offline

Windows desktop software for creating timed Bangla subtitles completely offline, editing subtitle text and style, placing a logo, adjusting video color, and exporting a new MP4.

## What changed in V2

- No OpenAI API key, billing, account, or Internet connection is required.
- Transcription runs locally with `whisper.cpp` and the multilingual Whisper Medium Q5 model.
- The AI engine and model are included in the Windows installer.
- Existing subtitle editing, SRT, logo, color, project, preview, and export features remain available.

The offline installer is larger because it contains the approximately 539 MB language model. Processing speed depends on the computer's CPU. The video and extracted audio remain on the computer.

## Download

Download `Bangla_Subtitle_Studio_Offline_Setup_V2.exe` from the `v2.0.0` GitHub Release and install it normally. The existing V1 installation can be upgraded because the installer keeps the same application identity.

## Developer build

The GitHub Actions workflow builds and bundles:

- Python runtime and the application
- FFmpeg, FFprobe, and FFplay
- statically built `whisper.cpp` CLI
- verified `ggml-medium-q5_0.bin` multilingual model
- Inno Setup installer and SHA-256 checksum

Complete Bangla usage instructions: [README_BN.md](README_BN.md)

Third-party notices: [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)
