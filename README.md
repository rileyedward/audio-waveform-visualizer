# Audio Waveform Visualizer

Render artistic visualizer videos for your DJ mixes — with optional local track identification, dynamic on-screen tracklist overlays, and YouTube chapter markers.

## Overview

### What is Audio Waveform Visualizer?

Audio Waveform Visualizer is a local command-line application designed to turn your DJ mixes into uploadable, YouTube-ready visualizer videos. Feed it a WAV or MP3 of your mix, pick a visual style and color palette, and it produces a polished 1080p30 H.264 MP4 with a reactive waveform, your artist/mix title, an optional logo, and a progress bar. Runs entirely on your machine — no uploads, no accounts, no cloud dependencies.

On top of that, point it at a folder of your source tracks (your DJ crate) and it will fingerprint that folder, auto-identify which track plays when in your mix, overlay the currently-playing track name on the video (crossfaded with a "NEXT:" peek between tracks), emit a timestamped YouTube-ready tracklist, and embed MP4 chapter markers. No external APIs, no cloud — entirely local.

### Why Use Audio Waveform Visualizer?

Posting a mix to YouTube without visuals leaves it buried. Existing visualizer tools are either browser-based (capped at short clips), locked behind subscriptions, or require wrestling with video editing software for every release. Adding a tracklist, chapter markers, and "now playing" overlays compounds that pain — it usually means manually timing every song change. Audio Waveform Visualizer solves both problems with a scripted, repeatable pipeline: one command to build a fingerprint DB from your crate, one command per mix to render a fully-annotated video. Every mix gets the same treatment, from your own files, with full control over look and feel via configurable palettes and styles.

### Key Features

- **Four Visualizer Styles**: Choose from radial (Monstercat-style), horizontal bars, mirrored waveform, or reactive particle bloom.
- **Curated Color Palettes**: Six preset gradients (Sunset, Neon, Ocean, Mono, Forest, Ember) applied to both the background and the visualizer itself. Fully editable via JSON.
- **Text + Logo Overlays**: Show your artist name, mix title, and an optional circular-masked logo, positioned non-intrusively.
- **Progress Bar**: Always-on bottom bar so viewers can see how far through the mix they are.
- **Local Track Fingerprinting**: Scan your source-track folder once to build a SQLite fingerprint DB. No external services, no network.
- **Dynamic On-Screen Tracklist**: When a fingerprint DB is provided, the currently-playing track's name is rendered on the video. Between tracks it crossfades out while a "NEXT:" preview of the incoming track fades in.
- **YouTube Tracklist + Chapters**: Emit a `tracklist.txt` formatted for YouTube descriptions and embed MP4 chapter markers so YouTube auto-creates a chapter-split timeline on upload.
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

3. Verify the CLIs are available:

    ```bash
    .venv/bin/visualize --help
    .venv/bin/fingerprint-index --help
    ```

4. Render a visualizer for your mix (swap in your own filenames):

    ```bash
    .venv/bin/visualize \
      --input ~/Downloads/mix.wav \
      --output ~/Downloads/mix.mp4 \
      --style radial \
      --palette sunset \
      --artist "Riley Edward" \
      --mix-name "Live Mix | Disco Fever" \
      --title "First Transmissions (Soulful House / Nu Disco)" \
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

### Auto-Tracklist Setup (optional)

If you want the visualizer to detect and display each track in your mix automatically, you need to build a fingerprint database from the folder of source tracks you mixed from. This is a one-time step — rebuild only when you add new tracks to the crate.

1. Build the fingerprint database from a folder of your source tracks. The folder is scanned recursively; MP3, WAV, FLAC, M4A, AAC, and OGG are all supported. Track name and artist are read from ID3 tags (falling back to filenames in `Artist - Title` format).

    ```bash
    .venv/bin/fingerprint-index \
      --source-folder ~/Music/DJ-Crate \
      --db ~/.visualizer/fingerprints.db
    ```

2. Render a mix with auto-detected tracklist, YouTube description, and chapter markers:

    ```bash
    .venv/bin/visualize \
      --input ~/Downloads/mix.wav \
      --output ~/Downloads/mix.mp4 \
      --style radial \
      --palette sunset \
      --artist "Riley Edward" \
      --mix-name "Live Mix | Disco Fever" \
      --logo ~/Downloads/logo.png \
      --fingerprint-db ~/.visualizer/fingerprints.db \
      --auto-tracklist \
      --tracklist-out ~/Downloads/mix_tracklist.txt \
      --chapters
    ```

    - `--auto-tracklist` replaces the static `--title` line with a live track name that updates as each track plays, and crossfades to a "NEXT:" peek of the incoming track during transitions.
    - `--tracklist-out` writes a YouTube-ready description file with timestamps (`[MM:SS] Artist — Title`) that you can paste into your upload.
    - `--chapters` embeds MP4 chapter markers, so YouTube will automatically split the video into per-track chapters on upload.

3. When your crate changes, rebuild the index:

    ```bash
    .venv/bin/fingerprint-index \
      --source-folder ~/Music/DJ-Crate \
      --db ~/.visualizer/fingerprints.db \
      --rebuild
    ```

    Without `--rebuild`, already-indexed tracks are skipped on re-runs so adding a handful of new tracks is fast.

## Usage Reference

### `visualize` Flags

| Flag | Default | Notes |
|---|---|---|
| `--input / -i` | (required) | WAV or MP3, any length |
| `--output / -o` | (required) | MP4 path |
| `--style / -s` | (required) | `radial`, `bars`, `waveform`, `particles` |
| `--palette / -p` | (required) | `sunset`, `neon`, `ocean`, `mono`, `forest`, `ember` |
| `--artist` | `""` | DJ / channel name, rendered on the top line |
| `--mix-name` | `""` | Mix name; rendered on the same line as `--artist`, joined with ` - ` (e.g. `Riley Edward - Live Mix \| Disco Fever`) |
| `--title` | `""` | Smaller text below the header; ignored when `--auto-tracklist` is on and a track is detected |
| `--logo` | (none) | Image path; circular-masked, centered |
| `--fps` | `30` | |
| `--resolution` | `1920x1080` | `WxH` |
| `--n-bands` | `72` | Bands for radial/bars |
| `--crf` | `18` | x264 quality (lower = better, bigger) |
| `--preset` | `medium` | x264 speed/size tradeoff |
| `--duration` | full | Cap render length (seconds) — useful for previews |
| `--palettes-file` | bundled | Override palettes JSON |
| `--fingerprint-db` | (none) | Path to SQLite DB built by `fingerprint-index` |
| `--auto-tracklist` | off | Detect tracks against `--fingerprint-db` and overlay dynamic track text |
| `--tracklist-out` | (none) | Path to write YouTube-formatted `[MM:SS] Artist — Title` tracklist |
| `--chapters` | off | Embed MP4 chapter markers at detected track boundaries |

### `fingerprint-index` Flags

| Flag | Default | Notes |
|---|---|---|
| `--source-folder / -s` | (required) | Folder with source tracks; scanned recursively |
| `--db / -d` | (required) | Output SQLite database path |
| `--rebuild` | off | Delete the existing DB and rebuild from scratch |

### Styles

- `radial` — Monstercat-style bars arranged in a circle around the center
- `bars` — horizontal spectrum bars along the bottom
- `waveform` — mirrored oscilloscope line across the middle
- `particles` — pulsing bloom rings plus orbiting dots driven by RMS energy

### Palettes

Defined in `src/visualizer/palettes.json`. Each palette has a `bg` pair (two hex colors for the vertical gradient behind the viz) and a `viz` pair (two hex colors the visualizer interpolates between by magnitude). Add your own freely — the CLI picks them up by name.

### How Track Identification Works

The fingerprinter is a Shazam-style algorithm implemented from scratch and run fully locally:

1. Each source track is converted to mono at 22.05kHz, STFT'd, and spectral peaks are extracted (local maxima in the time-frequency grid).
2. Peaks are paired within a forward time window to produce robust `(f_anchor, f_target, Δt)` fingerprint hashes, stored in SQLite along with the source time offset.
3. When matching a mix, the same fingerprints are extracted from the mix audio. For each 10-second window, the DB is queried, matches are grouped by `(track_id, time_offset)`, and the winning track per window is chosen by vote count.
4. Contiguous windows with the same winner become `TrackSegment` entries; boundaries where two tracks both score highly become `TransitionZone` entries that drive the on-screen crossfade + "NEXT:" peek.

Matching is deterministic and offline. No network calls, no accounts, no external APIs. The whole pipeline — fingerprint extraction, DB query, segment merging, text overlay, FFmpeg chapter mux — is in `src/visualizer/fingerprint/` and `src/visualizer/tracklist.py`.
