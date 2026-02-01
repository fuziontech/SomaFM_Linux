"""Audio player using mpv for streaming."""

import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from models import Channel

MPV_SOCKET = Path("/tmp/somafm-mpv-socket")


class AudioPlayer:
    def __init__(self):
        self.is_playing = False
        self.current_channel: Optional[Channel] = None
        self.current_song: Optional[str] = None
        self._mpv_process: Optional[subprocess.Popen] = None
        self._on_state_change: Optional[Callable[[], None]] = None
        self._song_poll_thread: Optional[threading.Thread] = None
        self._stop_polling = threading.Event()

    def set_on_state_change(self, callback: Callable[[], None]) -> None:
        """Set callback for when playback state changes."""
        self._on_state_change = callback

    def play(self, channel: Channel) -> None:
        """Start playing a channel."""
        self.stop()

        self.current_channel = channel
        self._start_mpv(channel.stream_url)
        self.is_playing = True

        self._notify_state_change()
        self._start_song_polling()

    def stop(self) -> None:
        """Stop playback."""
        self._stop_polling.set()
        if self._song_poll_thread:
            self._song_poll_thread.join(timeout=1)
            self._song_poll_thread = None

        self._kill_mpv()
        self.is_playing = False
        self.current_song = None
        self._notify_state_change()

    def pause(self) -> None:
        """Pause playback."""
        self._send_mpv_command({"command": ["set_property", "pause", True]})
        self.is_playing = False
        self._stop_polling.set()
        self._notify_state_change()

    def resume(self) -> None:
        """Resume playback."""
        self._send_mpv_command({"command": ["set_property", "pause", False]})
        self.is_playing = True
        self._stop_polling.clear()
        self._start_song_polling()
        self._notify_state_change()

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        if self.is_playing:
            self.pause()
        elif self.current_channel:
            self.resume()

    def _start_mpv(self, url: str) -> None:
        """Start mpv process with IPC socket."""
        # Clean up old socket
        if MPV_SOCKET.exists():
            MPV_SOCKET.unlink()

        self._mpv_process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                "--no-terminal",
                f"--input-ipc-server={MPV_SOCKET}",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for socket to be created
        for _ in range(20):
            if MPV_SOCKET.exists():
                break
            time.sleep(0.1)

    def _kill_mpv(self) -> None:
        """Kill the mpv process."""
        if self._mpv_process:
            self._mpv_process.terminate()
            try:
                self._mpv_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._mpv_process.kill()
            self._mpv_process = None

        if MPV_SOCKET.exists():
            MPV_SOCKET.unlink()

    def _send_mpv_command(self, command: dict) -> Optional[dict]:
        """Send a command to mpv via IPC socket."""
        if not MPV_SOCKET.exists():
            return None

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(str(MPV_SOCKET))
            sock.sendall((json.dumps(command) + "\n").encode())
            sock.settimeout(1.0)
            response = sock.recv(4096).decode()
            sock.close()
            return json.loads(response)
        except (socket.error, json.JSONDecodeError):
            return None

    def _start_song_polling(self) -> None:
        """Start polling for current song info."""
        self._stop_polling.clear()

        def poll():
            while not self._stop_polling.is_set():
                if self.current_channel and self.is_playing:
                    self._fetch_current_song()
                self._stop_polling.wait(30)

        self._song_poll_thread = threading.Thread(target=poll, daemon=True)
        self._song_poll_thread.start()

        # Fetch immediately
        if self.current_channel:
            threading.Thread(target=self._fetch_current_song, daemon=True).start()

    def _fetch_current_song(self) -> None:
        """Fetch current song from SomaFM API."""
        if not self.current_channel:
            return

        from channel_manager import ChannelManager

        manager = ChannelManager()
        song = manager.get_current_song(self.current_channel.id)

        if song != self.current_song:
            self.current_song = song
            self._notify_state_change()

    def _notify_state_change(self) -> None:
        """Notify listener of state change."""
        if self._on_state_change:
            self._on_state_change()
