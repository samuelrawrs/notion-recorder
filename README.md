# Notion Recorder

No-echo meeting audio for **Notion AI Meeting Notes** on Linux.

Notion Recorder creates a capture-only PipeWire/PulseAudio virtual microphone
(**Notion Meeting Mix**) that blends your physical microphone with the selected
speaker output, so Notion transcribes both sides of a call from a single input.
The mix is never routed back to playback, so remote participants never hear an
echo, and your system default microphone is left untouched (Google Meet, Zoom
and Teams keep using it unchanged).

It ships as a GTK4/libadwaita app with live level meters, friendly device
pickers, an audio-flow diagram, an optional mic-activity daemon that can
auto-start and stop the mix around your calls, and an optional system-tray icon.

> Requires a Debian/Ubuntu system with PipeWire (`pipewire-pulse`) or PulseAudio.

## Install

### Recommended: apt repository

Gets you `apt install notion-recorder` and automatic updates via `apt upgrade`.

```bash
curl -fsSL https://samuelrawrs.github.io/notion-recorder/notion-recorder.gpg \
  | sudo tee /usr/share/keyrings/notion-recorder.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/notion-recorder.gpg] https://samuelrawrs.github.io/notion-recorder stable main" \
  | sudo tee /etc/apt/sources.list.d/notion-recorder.list
sudo apt update
sudo apt install notion-recorder
```

### Or: a single .deb

Grab `notion-recorder_<version>_all.deb` from the
[Releases page](https://github.com/samuelrawrs/notion-recorder/releases) and:

```bash
sudo apt install ./notion-recorder_1.0.0_all.deb
```

`apt` pulls the dependencies (`pulseaudio-utils`, `python3-gi`, `gir1.2-gtk-4.0`,
`gir1.2-adw-1`, and cairo bindings) automatically either way.

## Use for a meeting

1. Connect and select your external microphone and headphones.
2. Open **Notion Recorder** and start the mix.
3. In Notion, begin a fresh transcript and select **Notion Meeting Mix** as the microphone.
4. Google Meet, Zoom, and Teams keep using your physical microphone automatically. The mix never changes your system default input, so participants can never hear an echo.
5. When done, stop transcription in Notion, then stop the mix.

If you change microphone or output device, stop transcription, restart the mix,
hard-reload Notion, then begin a fresh transcript.

**Verify:** say a short phrase, then play a few seconds of a YouTube clip through
the selected headphones. Both should appear in Notion, and remote participants
must not hear their own speech echoed back.

## Auto-start (optional)

A background daemon can start the mix automatically when it detects an app
capturing your microphone (a call starting) and stop it shortly after the call
ends. It is **off by default**. Toggle it from the app's Configuration page, or
manually:

```bash
systemctl --user enable --now notion-recorder-daemon.service   # enable
systemctl --user disable --now notion-recorder-daemon.service  # disable
```

The daemon only reads stream metadata from `pactl`; it never inspects audio
samples, and it only auto-stops a mix that it started itself.

## Tray icon (optional)

Turn on **Show a tray icon** on the Configuration page to add a top-bar menu
that starts or stops the mix without opening the main window, and survives
closing it. It runs as a small separate helper (`notion-recorder-tray`) and
starts automatically on login while enabled.

The tray needs an AppIndicator typelib (`gir1.2-ayatanaappindicator3-0.1`),
which the package recommends and `apt` installs by default. On GNOME it also
needs the AppIndicator shell extension (preinstalled on Ubuntu); most other
desktops (KDE, Cinnamon, Budgie, XFCE, MATE) show it natively.

## Command line

```bash
notion-meeting-audio start | stop | restart | status | toggle
```

## Uninstall

```bash
sudo apt remove notion-recorder
# if you added the apt repository:
sudo rm -f /etc/apt/sources.list.d/notion-recorder.list /usr/share/keyrings/notion-recorder.gpg
```

## Build from source

```bash
make deb                 # build notion-recorder_<version>_all.deb into ../
sudo apt install ../notion-recorder_*.deb

# or install straight into a prefix without packaging:
sudo make install                    # into /usr
make install PREFIX=$HOME/.local     # per-user, no root
```

Releases and the apt repository are produced automatically by
`.github/workflows/release.yml` when a `v*.*.*` tag is pushed (see the workflow
for the one-time `GPG_PRIVATE_KEY` secret and GitHub Pages setup).

## Consent

Obtain the consent required by the participants and applicable law before
recording or transcribing a meeting.

## License

MIT. See [LICENSE](LICENSE).
