# Notion Recorder

Notion Recorder is a Linux PipeWire/PulseAudio bridge for Notion AI Meeting
Notes. It mixes the selected microphone with the monitor of the selected audio
output, then exposes that mix as a virtual microphone.

The mix has no path back to playback. It captures both sides of a call without
creating an audio-feedback loop.

An optional background daemon can auto-start the mix when you use the mic during
a meeting and stop it afterwards (see `AUTOSTART.md`).

## Requirements

- Linux with PipeWire and `pipewire-pulse`, or PulseAudio
- `pactl` and `parec` (from `pulseaudio-utils`)
- Python 3 with GTK 4 and libadwaita (`python3-gi`, `gir1.2-gtk-4.0`, `gir1.2-adw-1`) for the desktop app

## Install with Flatpak

```bash
flatpak install flathub org.gnome.Sdk//48 org.gnome.Platform//48
flatpak-builder --user --install --force-clean build-dir \
    io.github.samuelrawrs.NotionRecorder.yaml
flatpak run io.github.samuelrawrs.NotionRecorder
```

The Flatpak bundles the `pactl`/`parec` client tools and reaches the host
PipeWire/PulseAudio through `--socket=pulseaudio`. Note: the optional
mic-activity auto-start daemon does not run inside the sandbox; use the
source install below if you want auto-start. See `FLATPAK.md` for details.

## Install locally

```bash
make install
```

Open **Notion Recorder** from the desktop app launcher, or run the CLI directly:

```bash
notion-meeting-audio start
```

## Use for a meeting

1. Connect and select the external microphone and headphones.
2. Start the bridge.
3. In Notion, begin a fresh transcript and select **Notion Meeting Mix** as the microphone.
4. Google Meet, Zoom, and Teams keep using your physical microphone automatically. The bridge never changes your system default input, so participants can never hear an echo.
5. At the end, stop transcription, then stop the bridge.

If a microphone or output device changes, stop transcription, restart the bridge,
hard-reload Notion, then begin a fresh transcript.

## Verify

Run a short local-mic phrase, then play a short YouTube clip through the selected
headphones. Both should appear in Notion. Remote meeting participants must not
hear their own speech echoed back.

## Commands

```bash
notion-meeting-audio start
notion-meeting-audio stop
notion-meeting-audio restart
notion-meeting-audio status
notion-meeting-audio toggle
```

## Auto-start (optional)

A background daemon can start the mix automatically on mic activity and stop it
when the meeting ends. It is opt-in and not enabled by `make install`; see
`AUTOSTART.md` to enable it.

## Distribution status

Both a local `make install` and a Flatpak build are supported. The Flatpak
bundles the PulseAudio client tools (`pactl`/`parec`) and reaches the host
PipeWire/PulseAudio through explicit audio permissions; see `FLATPAK.md`.

## Consent

Obtain the consent required by the participants and applicable law before
recording or transcribing a meeting.
