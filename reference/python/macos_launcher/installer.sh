#!/bin/sh
set -eu

# Arvectum OS — macOS Desktop App Installer
#
# Creates/updates ~/Desktop/Arvectum OS.app as a Finder-launchable
# Workspace launcher. The generated .app is NOT tracked in git.
#
# Usage:
#   sh reference/python/macos_launcher/installer.sh install
#   sh reference/python/macos_launcher/installer.sh uninstall
#   sh reference/python/macos_launcher/installer.sh status

APP_NAME="Arvectum OS"
APP_PATH="$HOME/Desktop/$APP_NAME.app"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
LAUNCHER_SCRIPT="$SCRIPT_DIR/launcher.sh"
RUNTIME_ROOT="${ARVECTUM_P7_02_ROOT:-$HOME/Library/Application Support/ArvectumOS/persistent-internal}"
LABEL="com.arvectum.os.persistent-internal"
LAUNCHER_LOG="$RUNTIME_ROOT/logs/desktop-launcher.log"
WORKSPACE_URL="http://127.0.0.1:8769"
OPEN=/usr/bin/open
LAUNCHCTL=/bin/launchctl
CURL=/usr/bin/curl
APPLESCRIPT=/usr/bin/osascript

fail() { printf '%s\n' "Installer FAIL: $*" >&2; exit 1; }
info() { printf '%s\n' "Installer: $*"; }

check_prerequisites() {
  [ -d "$RUNTIME_ROOT" ] || fail "Arvectum OS runtime not found at $RUNTIME_ROOT. Run P7.02 install first."
  [ -L "$RUNTIME_ROOT/current" ] || fail "Arvectum OS current release not installed. Run P7.02 install first."
  [ -f "$LAUNCHER_SCRIPT" ] || fail "Launcher script not found at $LAUNCHER_SCRIPT"
  [ -x "$LAUNCHER_SCRIPT" ] || chmod +x "$LAUNCHER_SCRIPT"
}

build_app() {
  info "Building $APP_NAME.app"

  rm -rf "$APP_PATH"
  mkdir -p "$APP_PATH/Contents/MacOS"
  mkdir -p "$APP_PATH/Contents/Resources"

  cp "$LAUNCHER_SCRIPT" "$APP_PATH/Contents/MacOS/$APP_NAME"
  chmod +x "$APP_PATH/Contents/MacOS/$APP_NAME"

  cat > "$APP_PATH/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>Arvectum OS</string>
    <key>CFBundleIdentifier</key>
    <string>com.arvectum.os.desktop-launcher</string>
    <key>CFBundleName</key>
    <string>Arvectum OS</string>
    <key>CFBundleDisplayName</key>
    <string>Arvectum OS</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Arvectum OS — Productive Workspace launcher</string>
</dict>
</plist>
PLIST

  printf '%s' 'APPL????' > "$APP_PATH/Contents/PkgInfo"

  info "$APP_NAME.app built at $APP_PATH"
}

install_app() {
  check_prerequisites
  build_app

  if [ -d "$APP_PATH" ] && [ -f "$APP_PATH/Contents/Info.plist" ] && [ -x "$APP_PATH/Contents/MacOS/$APP_NAME" ]; then
    info "Install PASS"
    info "  Location: $APP_PATH"
    info "  Double-click to open Arvectum OS Workspace"
    info "  Workspace URL: $WORKSPACE_URL"
  else
    fail "Installed app verification failed"
  fi
}

uninstall_app() {
  info "Uninstalling $APP_NAME.app"

  if [ -d "$APP_PATH" ]; then
    rm -rf "$APP_PATH"
    info "Removed $APP_PATH"
  else
    info "$APP_PATH not found; nothing to remove"
  fi

  local lock_dir="$RUNTIME_ROOT/run/desktop-launcher.lock"
  if [ -d "$lock_dir" ]; then
    rm -rf "$lock_dir"
    info "Removed launcher lock"
  fi

  info "Uninstall complete. Runtime and data remain at $RUNTIME_ROOT"
}

status_app() {
  printf '%s\n' "=== Arvectum OS Desktop Launcher ==="
  printf '%s\n' ""

  if [ -d "$APP_PATH" ]; then
    printf '%s\n' "App:    installed at $APP_PATH"
    if [ -f "$APP_PATH/Contents/Info.plist" ]; then
      printf '%s\n' "  Info.plist: present"
    fi
    if [ -x "$APP_PATH/Contents/MacOS/$APP_NAME" ]; then
      printf '%s\n' "  Executable: present and executable"
    fi
  else
    printf '%s\n' "App:    not installed"
  fi

  printf '%s\n' ""

  local target="gui/$(id -u)/$LABEL"
  if "$LAUNCHCTL" print "$target" >/dev/null 2>&1; then
    local pid
    pid=$("$LAUNCHCTL" print "$target" 2>/dev/null | awk '/^[[:space:]]*pid = / {print $3; exit}')
    printf '%s\n' "Workspace: running (pid=$pid)"
    local http_code
    http_code=$("$CURL" -s -o /dev/null -w "%{http_code}" --max-time 3 "$WORKSPACE_URL/" 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
      printf '%s\n' "  HTTP: $WORKSPACE_URL returned $http_code"
    else
      printf '%s\n' "  HTTP: $WORKSPACE_URL returned $http_code (may still be starting)"
    fi
  else
    printf '%s\n' "Workspace: not running"
  fi

  printf '%s\n' ""
  printf '%s\n' "Logs: $LAUNCHER_LOG"
}

usage() {
  cat <<EOF
Usage: $0 install|uninstall|status

install     create or update ~/Desktop/$APP_NAME.app
uninstall   remove the Desktop app (runtime and data are preserved)
status      show installation and workspace status
EOF
}

case "${1:-}" in
  install) install_app ;;
  uninstall) uninstall_app ;;
  status) status_app ;;
  *) usage; exit 2 ;;
esac
