# Auto-start the Notion meeting mix

By default the bridge is manual: you click **Start bridge** (or run
`notion-meeting-audio start`) before a Notion transcript. This is optional and
turns that into a background daemon that starts the bridge automatically when you
are actually in a meeting, and stops it when you are done.

## What triggers it, and why

The daemon (`notion-recorder-daemon`) watches **microphone activity** and starts
the bridge the moment another application begins capturing your physical mic
(Google Meet, Zoom, Teams, any recorder), then stops it a few seconds after that
capture ends.

Mic activity was chosen over the alternatives because it is the only
**framework-agnostic** signal for "I am in a meeting or recording":

- It works identically for Google Meet, Zoom, Teams, Discord, OBS, etc. - anything
  that opens the microphone.
- Process / window / browser-tab detection (looking for a Meet tab or the Notion
  app) is fragile, browser-specific, and breaks whenever a vendor changes their
  UI or process names. It is mentioned only as a possible secondary heuristic; it
  is not what the daemon uses.

### The important subtlety it handles

Once the bridge is running it loads its own `module-loopback` that records from
the physical mic into the private mix sink. A naive "is the mic in use?" check
would see that loopback and **latch on forever**, so the bridge could never
auto-stop. The daemon counts only **external** capture streams on the physical
mic - it excludes:

- source-outputs owned by the bridge's own `notion_meeting_mix` modules (its mic
  loopback), and
- the app's own `parec` level meter (`application.name = "Notion Recorder Meter"`).

A short debounce (default 4 s) after external capture returns to zero prevents
flapping when you switch between apps.

## Privacy

The daemon never records or inspects audio. It only reads stream **metadata**
(stream indices, owner modules, application names) from `pactl`. No audio samples
are ever read by the daemon.

## Enable it (recommended: systemd --user)

Install the files (see the Makefile / `INTEGRATION.md`), then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now notion-recorder-daemon.service
```

Check it:

```bash
systemctl --user status notion-recorder-daemon.service
journalctl --user -u notion-recorder-daemon.service -f
```

Disable it (back to fully manual control):

```bash
systemctl --user disable --now notion-recorder-daemon.service
```

If your user session ends when you log out and you want the daemon to keep
running across logouts, enable lingering once: `loginctl enable-linger $USER`.

## Alternative: XDG autostart (no systemd user services)

For desktops without `systemd --user`, install
`data/notion-recorder-autostart.desktop` to `~/.config/autostart/`. It launches
`notion-recorder-daemon` at login (requires `~/.local/bin` on your `PATH`).
Remove that file to disable. systemd is preferred because it restarts the daemon
on failure and gives you `journalctl` logs.

## How it interacts with the manual UI toggle

- **Manual Start** in the app always wins: the daemon only auto-stops bridges it
  auto-started itself (tracked via a marker file in
  `$XDG_RUNTIME_DIR/notion-recorder/`). A bridge you started by hand is never
  torn down under you.
- **Manual Stop** during an active call: the daemon may re-start the bridge on
  its next check, because the mic is still in use. If you want full manual
  control, disable the daemon.
- With the daemon enabled you normally never touch the toggle: join a call, the
  bridge appears; leave the call, it goes away a few seconds later.

## Sharing the daemon with colleagues

The daemon is just three files plus the existing bridge:

| File | Installed to |
| --- | --- |
| `notion-recorder-daemon` | `~/.local/bin/notion-recorder-daemon` |
| `notion-meeting-audio` (already shipped) | `~/.local/bin/notion-meeting-audio` |
| `data/notion-recorder-daemon.service` | `~/.config/systemd/user/` (or `~/.local/share/systemd/user/`) |

Once `make install` has placed those files, each colleague enables it with the
two commands above:

```bash
systemctl --user daemon-reload
systemctl --user enable --now notion-recorder-daemon.service
```

That is the only daemon-specific step. General packaging / release instructions
live in the project's separate distribution guide; this document only covers the
enable/disable steps.
