"""Fetches and caches SomaFM channel data."""

import json
import os
from pathlib import Path
from typing import Callable, Optional

import requests

from models import Channel

CHANNELS_URL = "https://api.somafm.com/channels.json"
SONGS_URL = "https://api.somafm.com/songs/{channel_id}.json"
CACHE_DIR = Path.home() / ".cache" / "somafm"
CACHE_FILE = CACHE_DIR / "channels.json"


class ChannelManager:
    def __init__(self):
        self.channels: list[Channel] = []
        self._on_update: Optional[Callable[[], None]] = None

    def set_on_update(self, callback: Callable[[], None]) -> None:
        """Set callback to be called when channels are updated."""
        self._on_update = callback

    def fetch_channels(self) -> list[Channel]:
        """Fetch channels from API, falling back to cache on failure."""
        try:
            response = requests.get(CHANNELS_URL, timeout=10)
            response.raise_for_status()
            data = response.json()

            self.channels = [
                Channel.from_api(ch)
                for ch in data.get("channels", [])
                if ch.get("playlists")
            ]
            # Sort by listener count descending
            self.channels.sort(key=lambda c: c.listeners, reverse=True)

            self._cache_channels()

        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"Failed to fetch channels: {e}")
            self._load_cached_channels()

        if self._on_update:
            self._on_update()

        return self.channels

    def get_current_song(self, channel_id: str) -> Optional[str]:
        """Fetch the current song for a channel."""
        try:
            response = requests.get(
                SONGS_URL.format(channel_id=channel_id), timeout=5
            )
            response.raise_for_status()
            data = response.json()

            songs = data.get("songs", [])
            if songs:
                song = songs[0]
                artist = song.get("artist", "")
                title = song.get("title", "")
                if artist and title:
                    return f"{artist} - {title}"
                return title or None

        except (requests.RequestException, json.JSONDecodeError):
            pass

        return None

    def _cache_channels(self) -> None:
        """Save channels to cache file."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "id": ch.id,
                    "title": ch.title,
                    "description": ch.description,
                    "stream_url": ch.stream_url,
                    "image_url": ch.image_url,
                    "genre": ch.genre,
                    "listeners": ch.listeners,
                }
                for ch in self.channels
            ]
            CACHE_FILE.write_text(json.dumps(data))
        except OSError as e:
            print(f"Failed to cache channels: {e}")

    def _load_cached_channels(self) -> None:
        """Load channels from cache file."""
        try:
            if CACHE_FILE.exists():
                data = json.loads(CACHE_FILE.read_text())
                self.channels = [
                    Channel(
                        id=ch["id"],
                        title=ch["title"],
                        description=ch["description"],
                        stream_url=ch["stream_url"],
                        image_url=ch.get("image_url"),
                        genre=ch.get("genre"),
                        listeners=ch.get("listeners", 0),
                    )
                    for ch in data
                ]
        except (OSError, json.JSONDecodeError, KeyError) as e:
            print(f"Failed to load cached channels: {e}")
