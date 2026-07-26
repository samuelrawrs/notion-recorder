# Notion Recorder install rules.
#
# PREFIX defaults to /usr (the layout the .deb ships). For a manual, per-user
# install you can override it, e.g. `make install PREFIX=$HOME/.local`, but the
# supported distribution channel is the .deb (see README).
PREFIX ?= /usr
DESTDIR ?=
APP_ID = io.github.samuelrawrs.NotionRecorder

BINDIR = $(DESTDIR)$(PREFIX)/bin
APPDIR = $(DESTDIR)$(PREFIX)/share/applications
ICONDIR = $(DESTDIR)$(PREFIX)/share/icons/hicolor/scalable/apps
METAINFODIR = $(DESTDIR)$(PREFIX)/share/metainfo
# System-installed systemd *user* units live here; `systemctl --user` searches it.
USERUNITDIR = $(DESTDIR)$(PREFIX)/lib/systemd/user

check:
	bash -n notion-meeting-audio
	bash -n notion-recorder-daemon
	python3 -m py_compile notion-recorder.py
	python3 -m py_compile notion-recorder-tray

install: check
	install -Dm755 notion-meeting-audio $(BINDIR)/notion-meeting-audio
	install -Dm755 notion-recorder.py $(BINDIR)/notion-recorder
	install -Dm755 notion-recorder-daemon $(BINDIR)/notion-recorder-daemon
	install -Dm755 notion-recorder-tray $(BINDIR)/notion-recorder-tray
	install -Dm644 notion-recorder.desktop $(APPDIR)/$(APP_ID).desktop
	install -Dm644 data/$(APP_ID).svg $(ICONDIR)/$(APP_ID).svg
	install -Dm644 data/$(APP_ID).metainfo.xml $(METAINFODIR)/$(APP_ID).metainfo.xml
	install -Dm644 data/notion-recorder-daemon.service $(USERUNITDIR)/notion-recorder-daemon.service
	@# Refresh caches only for a direct local install; during packaging (DESTDIR
	@# set) dpkg triggers regenerate them, so shipping cache files would be wrong.
	@if [ -z "$(DESTDIR)" ]; then \
		gtk-update-icon-cache -qtf $(PREFIX)/share/icons/hicolor 2>/dev/null || true; \
		update-desktop-database -q $(APPDIR) 2>/dev/null || true; \
	fi

uninstall:
	rm -f $(BINDIR)/notion-meeting-audio
	rm -f $(BINDIR)/notion-recorder
	rm -f $(BINDIR)/notion-recorder-daemon
	rm -f $(BINDIR)/notion-recorder-tray
	rm -f $(APPDIR)/$(APP_ID).desktop
	rm -f $(ICONDIR)/$(APP_ID).svg
	rm -f $(METAINFODIR)/$(APP_ID).metainfo.xml
	rm -f $(USERUNITDIR)/notion-recorder-daemon.service
	@if [ -z "$(DESTDIR)" ]; then \
		gtk-update-icon-cache -qtf $(PREFIX)/share/icons/hicolor 2>/dev/null || true; \
		update-desktop-database -q $(APPDIR) 2>/dev/null || true; \
	fi

# Build the binary .deb (arch: all) into ../ using the debian/ packaging.
deb: check
	dpkg-buildpackage -us -uc -b

.PHONY: check install uninstall deb
