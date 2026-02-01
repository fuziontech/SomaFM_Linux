"""Data models for SomaFM channels and songs."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Channel:
    id: str
    title: str
    description: str
    stream_url: str
    image_url: Optional[str] = None
    genre: Optional[str] = None
    listeners: int = 0

    @classmethod
    def from_api(cls, data: dict) -> "Channel":
        """Create a Channel from SomaFM API response data."""
        # Get highest quality MP3 stream
        stream_url = ""
        for playlist in data.get("playlists", []):
            if playlist.get("format") == "mp3" and playlist.get("quality") == "highest":
                stream_url = playlist.get("url", "")
                break
        if not stream_url and data.get("playlists"):
            stream_url = data["playlists"][0].get("url", "")

        # Get best available image
        image_url = (
            data.get("xlimage") or data.get("largeimage") or data.get("image")
        )

        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            stream_url=stream_url,
            image_url=image_url,
            genre=data.get("genre"),
            listeners=int(data.get("listeners", 0) or 0),
        )
