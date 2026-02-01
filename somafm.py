#!/usr/bin/env python3
"""SomaFM Linux - A system tray player for SomaFM internet radio."""

import signal
import sys
import threading
import urllib.parse
import webbrowser

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AppIndicator3", "0.1")

from gi.repository import AppIndicator3, GLib, Gtk

from audio_player import AudioPlayer
from channel_manager import ChannelManager
from models import Channel

APP_ID = "somafm-linux"


class SomaFMApp:
    def __init__(self):
        self.channel_manager = ChannelManager()
        self.audio_player = AudioPlayer()

        # Set up callbacks
        self.channel_manager.set_on_update(self._on_channels_update)
        self.audio_player.set_on_state_change(self._on_playback_state_change)

        # Create indicator
        self.indicator = AppIndicator3.Indicator.new(
            APP_ID,
            "audio-volume-medium",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("SomaFM")

        # Create initial menu
        self.menu = Gtk.Menu()
        self._build_menu()
        self.indicator.set_menu(self.menu)

        # Set up left-click action via secondary activate
        self.indicator.connect("scroll-event", self._on_scroll)
        # AppIndicator3 doesn't support left-click directly,
        # so we use middle-click as play/pause toggle
        self.indicator.set_secondary_activate_target(self._create_play_pause_item())

        # Fetch channels in background
        threading.Thread(target=self.channel_manager.fetch_channels, daemon=True).start()

    def _create_play_pause_item(self) -> Gtk.MenuItem:
        """Create a menu item for play/pause toggle."""
        item = Gtk.MenuItem(label="Toggle Play/Pause")
        item.connect("activate", self._on_toggle_play_pause)
        return item

    def _build_menu(self) -> None:
        """Build the context menu."""
        # Clear existing items
        for child in self.menu.get_children():
            self.menu.remove(child)

        # Now playing section
        if self.audio_player.current_channel and self.audio_player.is_playing:
            now_playing = Gtk.MenuItem(
                label=f"▶ {self.audio_player.current_channel.title}"
            )
            now_playing.set_sensitive(False)
            self.menu.append(now_playing)

            if self.audio_player.current_song:
                song_item = Gtk.MenuItem(label=f"   🎵 {self.audio_player.current_song}")
                song_item.connect("activate", self._on_song_click)
                self.menu.append(song_item)

            self.menu.append(Gtk.SeparatorMenuItem())

        # Channel list
        if not self.channel_manager.channels:
            loading = Gtk.MenuItem(label="Loading channels...")
            loading.set_sensitive(False)
            self.menu.append(loading)
        else:
            for channel in self.channel_manager.channels:
                label = channel.title
                if channel.listeners:
                    label += f" ({channel.listeners})"

                item = Gtk.MenuItem(label=label)
                item.connect("activate", self._on_channel_select, channel)

                # Show checkmark for current channel
                if (
                    self.audio_player.current_channel
                    and self.audio_player.current_channel.id == channel.id
                ):
                    item.set_label(f"● {label}")

                self.menu.append(item)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Play/Pause control
        if self.audio_player.is_playing:
            pause_item = Gtk.MenuItem(label="⏸ Pause")
            pause_item.connect("activate", self._on_pause)
            self.menu.append(pause_item)
        elif self.audio_player.current_channel:
            play_item = Gtk.MenuItem(label="▶ Play")
            play_item.connect("activate", self._on_resume)
            self.menu.append(play_item)

        # Stop
        if self.audio_player.current_channel:
            stop_item = Gtk.MenuItem(label="⏹ Stop")
            stop_item.connect("activate", self._on_stop)
            self.menu.append(stop_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()

    def _update_icon(self) -> None:
        """Update the tray icon based on playback state."""
        if self.audio_player.is_playing:
            self.indicator.set_icon("media-playback-start")
        else:
            self.indicator.set_icon("audio-volume-medium")

    def _on_channels_update(self) -> None:
        """Called when channels are updated."""
        GLib.idle_add(self._build_menu)

    def _on_playback_state_change(self) -> None:
        """Called when playback state changes."""
        GLib.idle_add(self._build_menu)
        GLib.idle_add(self._update_icon)

    def _on_channel_select(self, widget: Gtk.MenuItem, channel: Channel) -> None:
        """Handle channel selection."""
        threading.Thread(
            target=self.audio_player.play, args=(channel,), daemon=True
        ).start()

    def _on_toggle_play_pause(self, widget: Gtk.MenuItem) -> None:
        """Toggle play/pause."""
        self.audio_player.toggle_play_pause()

    def _on_pause(self, widget: Gtk.MenuItem) -> None:
        """Pause playback."""
        self.audio_player.pause()

    def _on_resume(self, widget: Gtk.MenuItem) -> None:
        """Resume playback."""
        self.audio_player.resume()

    def _on_stop(self, widget: Gtk.MenuItem) -> None:
        """Stop playback."""
        self.audio_player.stop()

    def _on_song_click(self, widget: Gtk.MenuItem) -> None:
        """Open search menu for current song."""
        if not self.audio_player.current_song:
            return

        song = self.audio_player.current_song
        encoded = urllib.parse.quote(song)

        # Show submenu with search options
        submenu = Gtk.Menu()

        youtube = Gtk.MenuItem(label="Search on YouTube")
        youtube.connect(
            "activate",
            lambda w: webbrowser.open(
                f"https://www.youtube.com/results?search_query={encoded}"
            ),
        )
        submenu.append(youtube)

        spotify = Gtk.MenuItem(label="Search on Spotify")
        spotify.connect(
            "activate",
            lambda w: webbrowser.open(
                f"https://open.spotify.com/search/{encoded}"
            ),
        )
        submenu.append(spotify)

        submenu.show_all()
        submenu.popup(None, None, None, None, 0, Gtk.get_current_event_time())

    def _on_scroll(self, indicator, steps, direction) -> None:
        """Handle scroll events for volume (future feature)."""
        pass

    def _on_quit(self, widget: Gtk.MenuItem) -> None:
        """Quit the application."""
        self.audio_player.stop()
        Gtk.main_quit()

    def run(self) -> None:
        """Run the application."""
        # Handle SIGINT gracefully
        signal.signal(signal.SIGINT, lambda s, f: self._on_quit(None))
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, Gtk.main_quit)

        Gtk.main()


def main():
    app = SomaFMApp()
    app.run()


if __name__ == "__main__":
    main()
