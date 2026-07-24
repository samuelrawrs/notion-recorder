PREFIX ?= $(HOME)/.local
APP_ID = io.github.samuelrawrs.NotionRecorder

# Version is the single source of truth in notion-recorder.py (VERSION = "x.y.z").
VERSION := $(shell sed -n 's/^VERSION *= *"\([^"]*\)".*/\1/p' notion-recorder.py)
DIST_NAME = notion-recorder-$(VERSION)
DIST_TARBALL = $(DIST_NAME).tar.gz

# Files shipped in a source release. Kept explicit so the tarball is complete
# even when data/ is not yet committed (git archive would drop untracked files).
DIST_FILES = \
	Makefile \
	README.md \
	LICENSE \
	INSTALL.md \
	DISTRIBUTING.md \
	AUTOSTART.md \
	notion-meeting-audio \
	notion-recorder.py \
	notion-recorder-daemon \
	notion-recorder.desktop \
	data/$(APP_ID).svg \
	data/$(APP_ID).metainfo.xml \
	data/notion-recorder-daemon.service \
	data/notion-recorder-autostart.desktop

check:
	bash -n notion-meeting-audio
	python3 -m py_compile notion-recorder.py

install: check
	install -Dm755 notion-meeting-audio $(PREFIX)/bin/notion-meeting-audio
	install -Dm755 notion-recorder.py $(PREFIX)/bin/notion-recorder
	install -Dm755 notion-recorder-daemon $(PREFIX)/bin/notion-recorder-daemon
	install -Dm644 notion-recorder.desktop $(PREFIX)/share/applications/$(APP_ID).desktop
	install -Dm644 data/$(APP_ID).svg $(PREFIX)/share/icons/hicolor/scalable/apps/$(APP_ID).svg
	install -Dm644 data/$(APP_ID).metainfo.xml $(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
	install -Dm644 data/notion-recorder-daemon.service $(PREFIX)/share/systemd/user/notion-recorder-daemon.service
	-gtk-update-icon-cache -qtf $(PREFIX)/share/icons/hicolor 2>/dev/null || true
	-update-desktop-database -q $(PREFIX)/share/applications 2>/dev/null || true

uninstall:
	rm -f $(PREFIX)/bin/notion-meeting-audio
	rm -f $(PREFIX)/bin/notion-recorder
	rm -f $(PREFIX)/bin/notion-recorder-daemon
	rm -f $(PREFIX)/share/applications/$(APP_ID).desktop
	rm -f $(PREFIX)/share/icons/hicolor/scalable/apps/$(APP_ID).svg
	rm -f $(PREFIX)/share/metainfo/$(APP_ID).metainfo.xml
	rm -f $(PREFIX)/share/systemd/user/notion-recorder-daemon.service
	-gtk-update-icon-cache -qtf $(PREFIX)/share/icons/hicolor 2>/dev/null || true
	-update-desktop-database -q $(PREFIX)/share/applications 2>/dev/null || true

# Build a versioned source tarball (notion-recorder-<version>.tar.gz) whose
# contents unpack into a single top-level notion-recorder-<version>/ directory.
dist: check
	@test -n "$(VERSION)" || { echo "could not read VERSION from notion-recorder.py"; exit 1; }
	tar czf $(DIST_TARBALL) --transform 's,^,$(DIST_NAME)/,' $(DIST_FILES)
	@echo "Built $(DIST_TARBALL)"

.PHONY: check install uninstall dist
