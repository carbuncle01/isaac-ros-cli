# Copyright (c) 2025, NVIDIA CORPORATION. All rights reserved.
#
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto. Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

# Simple packaging utility for isaac-ros-cli

PACKAGE_NAME := isaac-ros-cli

# Convenience variable for the built .deb (lives one dir up when using dpkg-buildpackage)
DEB_GLOB := ../$(PACKAGE_NAME)_*.deb
DOCKER_DEB_OVERRIDE_DIR := .docker-deb-overrides
SYSTEM_DOCKER_DEB_OVERRIDE_DIR := /etc/$(PACKAGE_NAME)/$(DOCKER_DEB_OVERRIDE_DIR)

.PHONY: help all build install test upload clean distclean release print-deb clear-docker-overrides

help:
	@echo "Targets:"
	@echo "  make build           - Build Debian package (.deb)"
	@echo "  sudo make install    - Install built Debian and stage it as Docker override"
	@echo "  make test            - Run Python CLI unit tests"
	@echo "  make build-stamped   - Build Debian package (.deb) with timestamped version"
	@echo "  make timestamp       - Append timestamp suffix to debian/changelog"
	@echo "  make clean           - Remove staged packaging artifacts inside debian/"
	@echo "  make distclean       - Clean and remove built files in parent dir"
	@echo "  make print-deb       - Print the path to the built .deb (expects exactly one)"
	@echo "  sudo make clear-docker-overrides - Remove Docker Debian overrides"
	@echo ""

all: build

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -t . -v

timestamp:
	@set -e; \
	timestamp=$$(date +%Y%m%d%H%M%S); \
	sed -i "1s/)/.$$timestamp)/" debian/changelog; \
	echo "Updated debian version with timestamp suffix .$$timestamp"; \
	head -1 debian/changelog

build:
	@echo "Building Debian package for $(PACKAGE_NAME)..."
	DEB_BUILD_OPTIONS=nocheck dpkg-buildpackage -us -uc -b
	@echo "Build complete. Use 'make print-deb' to locate the .deb file."

install:
	@set -e; \
	if [ -n "$(DESTDIR)" ]; then \
		echo "Skipping host install during Debian package staging."; \
		exit 0; \
	fi; \
	if [ "$$(id -u)" -ne 0 ]; then \
		echo "Error: 'make install' must be run as root. Use 'sudo make install'." 1>&2; \
		exit 1; \
	fi; \
	deb="$$( $(MAKE) --no-print-directory -s print-deb )"; \
	echo "Installing host package from $$deb..."; \
	apt-get install -y "$$deb"; \
	mkdir -p "$(DOCKER_DEB_OVERRIDE_DIR)"; \
	rm -f "$(DOCKER_DEB_OVERRIDE_DIR)"/$(PACKAGE_NAME)_*.deb; \
	cp "$$deb" "$(DOCKER_DEB_OVERRIDE_DIR)/"; \
	if [ -n "$${SUDO_UID:-}" ] && [ -n "$${SUDO_GID:-}" ]; then \
		chown -R "$$SUDO_UID:$$SUDO_GID" "$(DOCKER_DEB_OVERRIDE_DIR)"; \
	fi; \
	mkdir -p "$(SYSTEM_DOCKER_DEB_OVERRIDE_DIR)"; \
	rm -f "$(SYSTEM_DOCKER_DEB_OVERRIDE_DIR)"/$(PACKAGE_NAME)_*.deb; \
	cp "$$deb" "$(SYSTEM_DOCKER_DEB_OVERRIDE_DIR)/"; \
	echo "Staged source-local Docker Debian override: $(DOCKER_DEB_OVERRIDE_DIR)/$$(basename "$$deb")"; \
	echo "Staged Docker Debian override: $(SYSTEM_DOCKER_DEB_OVERRIDE_DIR)/$$(basename "$$deb")"; \
	echo "Docker builds driven by the installed CLI will use this override until it is cleared."

build-stamped:
	cp debian/changelog debian/changelog.original
	make timestamp
	make build
	mv debian/changelog.original debian/changelog

print-deb:
	@set -e; \
	count=$$(ls -1 $(DEB_GLOB) 2>/dev/null | wc -l | tr -d ' '); \
	if [ "$$count" -ne 1 ]; then \
		echo "Error: expected exactly one .deb matching $(DEB_GLOB), found $$count" 1>&2; \
		exit 1; \
	fi; \
	ls -1 $(DEB_GLOB)

clean:
	@echo "Removing staged packaging artifacts under debian/..."
	rm -rf debian/$(PACKAGE_NAME) debian/*.debhelper debian/*.substvars debian/debhelper-build-stamp debian/files
	rm -rf $(DOCKER_DEB_OVERRIDE_DIR)

distclean: clean
	@echo "Removing built artifacts in parent directory (if any)..."
	rm -f ../$(PACKAGE_NAME)_*.deb ../$(PACKAGE_NAME)_*.buildinfo ../$(PACKAGE_NAME)_*.changes

clear-docker-overrides:
	@rm -rf $(DOCKER_DEB_OVERRIDE_DIR)
	@if [ "$$(id -u)" -eq 0 ]; then \
		rm -rf "$(SYSTEM_DOCKER_DEB_OVERRIDE_DIR)"; \
		echo "Removed source-local and system Docker Debian overrides."; \
	else \
		echo "Removed source-local Docker Debian overrides."; \
		echo "Run 'sudo make clear-docker-overrides' to also remove $(SYSTEM_DOCKER_DEB_OVERRIDE_DIR)."; \
	fi
