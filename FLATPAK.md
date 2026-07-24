# Flatpak packaging

`io.github.samuelrawrs.NotionRecorder.yaml` is a Flathub-conventional manifest that
packages the GTK4/libadwaita app plus its PipeWire bridge as a one-click install.

## Build and install locally

```bash
# 1. Install the SDK + runtime (48 is Flathub-stable; see the note below).
flatpak install flathub org.gnome.Sdk//48 org.gnome.Platform//48

# 2. Build and install into the per-user Flatpak installation.
flatpak-builder --user --install --force-clean build-dir \
    io.github.samuelrawrs.NotionRecorder.yaml
```

### Runtime version note

The manifest pins `runtime-version: "48"` (current Flathub-stable). The machine
this was authored on only has GNOME runtimes **49** and **50** installed, not 48.
If a local build fails to find `48`, either install it:

```bash
flatpak install flathub org.gnome.Sdk//48 org.gnome.Platform//48
```

or bump `runtime-version` in the manifest to `49`/`50` and install the matching
SDK (`flatpak install flathub org.gnome.Sdk//50 org.gnome.Platform//50`).

## Run

```bash
flatpak run io.github.samuelrawrs.NotionRecorder
```

## Why `pactl`/`parec` are bundled

The app and the `notion-meeting-audio` bridge shell out to `pactl` and `parec`
(the PulseAudio client tools). The GNOME runtime does **not** ship these, so the
manifest builds them from the released PulseAudio 17.0 source as a separate
`pulseaudio-utils` module, with the daemon/server, docs, and every optional
server feature disabled. Only `libpulse`, `pactl`, and `parec` land in
`/app/bin`. `libsndfile` (needed by `parec`) already ships in the runtime.

## Audio permission rationale

`finish-args` grants:

- `--socket=wayland`, `--socket=fallback-x11`, `--share=ipc`, `--device=dri` —
  standard GTK4 display access.
- `--socket=pulseaudio` — the important one. It connects the sandboxed
  `pactl`/`parec` to the host `pipewire-pulse` (or PulseAudio) daemon. The
  bridge's null-sink / loopback / remap-source modules are created **server-side**
  on the host, so the routing works even though the daemon lives outside the
  sandbox.

## Limitation: no systemd auto-start inside the sandbox

The optional mic-activity auto-start daemon relies on a `systemd --user` unit
(`notion-recorder-daemon.service`). A Flatpak app cannot register or drive host
`systemd --user` units from inside the sandbox, so **auto-start does not work in
the Flatpak build**. The Flatpak targets manual/GUI use: open the app, start and
stop the mix by hand.

Auto-start remains fully available via the source / `make install` path — see
`AUTOSTART.md`.

## Flathub submission

1. Fork [flathub/flathub](https://github.com/flathub/flathub).
2. Add `io.github.samuelrawrs.NotionRecorder.yaml`, swapping the app module's
   `type: dir` source for a pinned `git` source (url + tag + commit) as shown in
   the manifest comment.
3. Open a PR against `flathub/flathub` (new-submissions process).
