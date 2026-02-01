# CLAUDE.md

This file provides context for Claude Code when working on this project.

## Project Overview

**SomaFM Linux** is a native Linux system tray application for streaming SomaFM internet radio channels. It's a Python port of the [macOS SomaFM Miniplayer](https://github.com/fuziontech/SomaFM).

- **Platform:** Linux (GNOME, KDE, XFCE, etc.)
- **Language:** Python 3
- **UI Framework:** GTK3 with AppIndicator3

## Tech Stack

- **UI:** PyGObject (GTK3) + AppIndicator3 for system tray
- **Audio:** mpv (via subprocess with IPC socket)
- **Networking:** requests for API calls
- **State Management:** Callbacks between components

## Project Structure

```
├── somafm.py           # Main entry point, tray icon, menu management
├── audio_player.py     # mpv wrapper with IPC for playback control
├── channel_manager.py  # Fetches/caches channel data from API
├── models.py           # Channel dataclass
└── requirements.txt    # Python dependencies
```

## Key Components

### SomaFMApp (`somafm.py`)
- Creates AppIndicator3 system tray icon
- Builds dynamic context menu with channels
- Handles user interactions (channel select, play/pause, search)

### AudioPlayer (`audio_player.py`)
- Manages mpv subprocess for streaming
- Uses Unix socket IPC for pause/resume control
- Polls SomaFM API every 30 seconds for current song

### ChannelManager (`channel_manager.py`)
- Fetches channels from `https://api.somafm.com/channels.json`
- Caches to `~/.cache/somafm/channels.json` for offline fallback
- Sorts channels by listener count (descending)

### Channel (`models.py`)
- Dataclass representing a SomaFM channel
- Parses API response, selects highest quality MP3 stream

## Commands

```bash
# Install system dependencies (Fedora)
sudo dnf install mpv python3-gobject gtk3 libappindicator-gtk3

# Install Python dependencies
pip install -r requirements.txt

# Run the application
./somafm.py
```

## API Endpoints

- **Channels:** `https://api.somafm.com/channels.json`
- **Current Song:** `https://api.somafm.com/songs/{channelId}.json`

## Architecture Notes

- AppIndicator3 doesn't support left-click action directly; middle-click is used for play/pause toggle
- mpv IPC socket is created at `/tmp/somafm-mpv-socket`
- All network/playback operations run in background threads to keep UI responsive
- GLib.idle_add() is used to safely update GTK from background threads
