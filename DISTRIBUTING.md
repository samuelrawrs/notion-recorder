# Distributing Notion Recorder

This is the maintainer's guide for shipping a release that colleagues can
download and install. End-user install steps live in [INSTALL.md](INSTALL.md).

## Recommended path

Ship a **versioned source tarball attached to a GitHub Release**. Colleagues
download the tarball, install the runtime deps once, and run `make install`.

This is the right choice because Notion Recorder depends on the host's `pactl`
and `parec` and on the live PipeWire/PulseAudio session. A source install runs
directly against the user's audio stack with no sandbox in the way. See
[Packaging feasibility](#packaging-feasibility) for why Flatpak/AppImage/.deb
are not recommended here.

## Versioning

The version is a single source of truth: `VERSION = "x.y.z"` near the top of
`notion-recorder.py`. The `make dist` target reads it automatically, so the
tarball name always matches the app version. Bump that constant before cutting
a release.

## Release checklist

1. Bump `VERSION` in `notion-recorder.py` if needed, and sanity-check:

   ```bash
   make check
   ```

2. Commit and tag. Match the tag to the app version:

   ```bash
   git add -A
   git commit -m "Release vX.Y.Z"
   git tag -a vX.Y.Z -m "Notion Recorder X.Y.Z"
   git push origin master --tags
   ```

3. Build the tarball:

   ```bash
   make dist
   # -> notion-recorder-X.Y.Z.tar.gz
   ```

4. Create the GitHub Release and attach the tarball (requires the `gh` CLI,
   authenticated with `gh auth login`):

   ```bash
   gh release create vX.Y.Z notion-recorder-X.Y.Z.tar.gz \
     --title "Notion Recorder X.Y.Z" \
     --notes "See INSTALL.md for setup. Requires PipeWire/PulseAudio with pactl."
   ```

   The tarball unpacks into a single `notion-recorder-X.Y.Z/` directory
   containing everything needed to `make install`.

## What colleagues run to install

Point them at the Release page, or give them these commands:

```bash
# 1. Install deps once (Debian/Ubuntu; see INSTALL.md for Fedora)
sudo apt update && sudo apt install \
  python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 pipewire-pulse

# 2. Download + unpack the release tarball
tar xzf notion-recorder-X.Y.Z.tar.gz
cd notion-recorder-X.Y.Z

# 3. Install into ~/.local (no root)
make install

# 4. Run
notion-recorder
```

To uninstall later, from the same directory: `make uninstall`.

## Alternative distribution options

### (a) Git clone + `make install` (simplest for teammates who use git)

```bash
git clone <REPO_URL> notion-recorder
cd notion-recorder
make install
```

- Pros: no release step; always gets the latest `master`; trivial to update
  with `git pull && make install`.
- Cons: no pinned version; colleagues need repo access and git; a broken commit
  ships immediately.

### (b) Versioned source tarball, shared directly

```bash
make dist            # builds notion-recorder-X.Y.Z.tar.gz
```

Hand the tarball to colleagues (Slack, shared drive, email). They unpack and
`make install` as above.

- Pros: pinned, reproducible version; no repo access needed; self-contained.
- Cons: manual delivery; no central download page (that's what option (c)
  adds).

### (c) GitHub Releases (recommended — see checklist above)

- Pros: stable download URLs per version; release notes; colleagues just click
  a link; pairs naturally with `make dist`.
- Cons: one-time `gh` setup; requires the repo to be on GitHub.

## Packaging feasibility

Not recommended for this tool, in short:

- **Flatpak**: the sandbox cannot rely on the host `pactl`/`parec` executables,
  which this bridge shells out to. Making it work means bundling a PulseAudio
  client or rewriting against a native PipeWire control API, plus wiring
  explicit audio permissions. High effort for a personal tool. (README also
  notes this.)
- **AppImage**: can bundle the GTK4/libadwaita stack, but `pactl`/`parec` and
  correct PipeWire session integration are awkward to carry portably, and the
  app still needs the host audio daemon. Marginal benefit over a source
  tarball.
- **.deb**: workable in principle (declare deps on `python3-gi`, `gir1.2-gtk-4.0`,
  `gir1.2-adw-1`, `pipewire-pulse`) but it installs system-wide, needs an apt
  repo or manual `dpkg -i` distribution, and only helps Debian/Ubuntu users.
  Overkill for sharing with a handful of colleagues.

Given the hard dependency on host `pactl`/PipeWire, a source tarball + GitHub
Release is both the least work and the most reliable option.
