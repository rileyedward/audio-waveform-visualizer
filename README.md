# Audio Visualizer

Render artistic visualizer videos for your DJ mixes.

## Overview

### What is Audio Visualizer?

Audio Visualizer is a local command-line application designed to turn your DJ mixes into uploadable, YouTube-ready visualizer videos. Feed it a WAV or MP3 of your mix, pick a visual style and color palette, and it produces a polished 1080p30 H.264 MP4 with a reactive waveform, your artist/mix title, an optional logo, and a progress bar. Runs entirely on your machine — no uploads, no accounts, no cloud dependencies.

### Why Use Audio Visualizer?

Posting a mix to YouTube without visuals leaves it buried. Existing visualizer tools are either browser-based (capped at short clips), locked behind subscriptions, or require wrestling with video editing software for every release. Audio Visualizer solves this by giving you a scripted, repeatable pipeline: one command in, one video out. Every mix gets the same treatment, rendered from your own files, with full control over look and feel via configurable palettes and styles.

### Key Features

- **Four Visualizer Styles**: Choose from radial (Monstercat-style), horizontal bars, mirrored waveform, or reactive particle bloom.
- **Curated Color Palettes**: Six preset gradients (Sunset, Neon, Ocean, Mono, Forest, Ember) applied to both the background and the visualizer itself. Fully editable via JSON.
- **Text + Logo Overlays**: Show your artist name, mix title, and an optional circular-masked logo, positioned non-intrusively.
- **Progress Bar**: Always-on bottom bar so viewers can see how far through the mix they are.
- **YouTube-Ready Output**: 1080p 30fps H.264 video with 320kbps AAC audio, muxed directly via FFmpeg.

## Getting Started

### Prerequisites

Ensure you have the following prerequisites installed on your system. You can verify each installation by running the provided commands in your terminal.

1. **Python 3.11+** is required to run the application. Check if Python is installed by running:

    ```bash
    python3 --version
    ```

2. **FFmpeg** is used for video encoding and audio muxing. Confirm FFmpeg is installed by running:

    ```bash
    ffmpeg -version
    ```

   If it is not installed, grab it with `brew install ffmpeg` on macOS.

### Installation

1. Create and activate a Python virtual environment in the project directory:

    ```bash
    python3 -m venv .venv
    ```

2. Install the project and its dependencies in editable mode:

    ```bash
    .venv/bin/pip install -e .
    ```

3. Verify the CLI is available:

    ```bash
    .venv/bin/visualize --help
    ```

4. Render a visualizer for your mix (swap in your own filenames):

    ```bash
    .venv/bin/visualize \
      --input ~/Downloads/mix.wav \
      --output ~/Downloads/mix.mp4 \
      --style radial \
      --palette sunset \
      --artist "Riley Edward" \
      --title "First Transmissions | Disco Fever (Soulful House / Nu Disco)" \
      --logo ~/Downloads/logo.png
    ```

5. For a quick preview before committing to a full render, cap the duration:

    ```bash
    .venv/bin/visualize -i mix.wav -o preview.mp4 -s radial -p sunset --duration 30
    ```

6. Run the bundled smoke-test script to generate one MP4 per style/palette combo:

    ```bash
    ./examples/sample_usage.sh
    ```

## Usage Reference

### Flags

| Flag | Default | Notes |
|---|---|---|
| `--input / -i` | (required) | WAV or MP3, any length |
| `--output / -o` | (required) | MP4 path |
| `--style / -s` | (required) | `radial`, `bars`, `waveform`, `particles` |
| `--palette / -p` | (required) | `sunset`, `neon`, `ocean`, `mono`, `forest`, `ember` |
| `--artist` | `""` | Small text, bottom-left |
| `--title` | `""` | Smaller text below artist |
| `--logo` | (none) | Image path; circular-masked, centered |
| `--fps` | `30` | |
| `--resolution` | `1920x1080` | `WxH` |
| `--n-bands` | `72` | Bands for radial/bars |
| `--crf` | `18` | x264 quality (lower = better, bigger) |
| `--preset` | `medium` | x264 speed/size tradeoff |
| `--duration` | full | Cap render length (seconds) — useful for previews |
| `--palettes-file` | bundled | Override palettes JSON |

### Styles

- `radial` — Monstercat-style bars arranged in a circle around the center
- `bars` — horizontal spectrum bars along the bottom
- `waveform` — mirrored oscilloscope line across the middle
- `particles` — pulsing bloom rings plus orbiting dots driven by RMS energy

### Palettes

Defined in `src/visualizer/palettes.json`. Each palette has a `bg` pair (two hex colors for the vertical gradient behind the viz) and a `viz` pair (two hex colors the visualizer interpolates between by magnitude). Add your own freely — the CLI picks them up by name.
