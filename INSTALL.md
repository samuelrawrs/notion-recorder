# Installing Notion Recorder

Notion Recorder is a small GTK4 / libadwaita desktop app plus a PipeWire /
PulseAudio bridge. It installs into your home directory (`~/.local`) and does
not need root.

## 1. Install the runtime dependencies

You need Python 3 with PyGObject (GTK 4 + libadwaita + cairo) and the PulseAudio
client tools (`pactl`, `parec`) from PipeWire's Pulse compatibility layer (or
from PulseAudio itself).

### Debian / Ubuntu

```bash
sudo apt update
sudo apt install \
  python3 \
  python3-gi \
  python3-gi-cairo \
  gir1.2-gtk-4.0 \
  gir1.2-adw-1 \
  pipewire-pulse
```

Notes:
- `pipewire-pulse` provides `pactl`/`parec` on a PipeWire system. If you run
  classic PulseAudio instead, install `pulseaudio-utils`.
- On older releases the libadwaita typelib may be packaged as
  `gir1.2-adwaita-1`; use whichever your distro provides.

### Fedora

```bash
sudo dnf install \
  python3 \
  python3-gobject \
  gtk4 \
  libadwaita \
  pipewire-pulseaudio
```

Notes:
- `python3-gobject` pulls in the cairo bindings on Fedora.
- `pipewire-pulseaudio` provides `pactl`/`parec`. On a PulseAudio host install
  `pulseaudio-utils` instead.

## 2. Get the source

Either clone the repository:

```bash
git clone <REPO_URL> notion-recorder
cd notion-recorder
```

or download and unpack a release tarball:

```bash
tar xzf notion-recorder-<version>.tar.gz
cd notion-recorder-<version>
```

## 3. Install

```bash
make install
```

This runs a syntax check, then copies the following into `~/.local`:

| File | Installed to |
| --- | --- |
| `notion-meeting-audio` | `~/.local/bin/notion-meeting-audio` |
| `notion-recorder.py` | `~/.local/bin/notion-recorder` |
| `notion-recorder.desktop` | `~/.local/share/applications/io.github.samuelrawrs.NotionRecorder.desktop` |
| `data/io.github.samuelrawrs.NotionRecorder.svg` | `~/.local/share/icons/hicolor/scalable/apps/` |
| `data/io.github.samuelrawrs.NotionRecorder.metainfo.xml` | `~/.local/share/metainfo/` |

It then refreshes the icon cache and desktop database (best effort).

If `~/.local/bin` is not already on your `PATH`, add it:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

## 4. Run it

Launch **Notion Recorder** from your application launcher, or use the CLI:

```bash
notion-recorder            # GTK app
notion-meeting-audio start # bridge only, no GUI
```

## 5. Uninstall

From the source directory:

```bash
make uninstall
```

This removes every file listed above from `~/.local`.

## Troubleshooting

- **App won't start / `No module named gi`**: PyGObject is missing. Reinstall
  the dependencies in step 1.
- **`pactl: command not found`**: install `pipewire-pulse`
  (`pipewire-pulseaudio` on Fedora) or `pulseaudio-utils`.
- **App launcher entry missing**: log out and back in, or run
  `update-desktop-database ~/.local/share/applications`.
