# Arvectum OS — macOS Desktop Launcher

## What is it

A Finder-launchable `Arvectum OS.app` that opens the Productive Workspace in your browser with a double-click. No Terminal or OpenCode needed for daily use.

## Install

```sh
sh reference/python/macos_launcher/installer.sh install
```

This creates `~/Desktop/Arvectum OS.app`.

## Uninstall

```sh
sh reference/python/macos_launcher/installer.sh uninstall
```

Removes only the Desktop app. Runtime, data and deployment remain intact.

## Status

```sh
sh reference/python/macos_launcher/installer.sh status
```

## What double-click does

1. If Workspace is already running → opens browser to `http://127.0.0.1:8769`
2. If Workspace is stopped → starts it via the existing P7.02 launchd service, waits for readiness, then opens browser
3. If startup fails → shows a native macOS error dialog with log location

## What double-click does NOT do

- No `git pull`, `git fetch`, or any update operation
- No dependency install
- No Terminal window
- No alternative runtime controller
- No autostart or Login Item

Launch ≠ Update. Use P7.06 for deploy/update/rollback.

## Logs

On failure, the error dialog shows the log path. Full diagnostic context:

```sh
cat ~/Library/Application\ Support/ArvectumOS/persistent-internal/logs/desktop-launcher.log
```

## Technical details

- Thin UX wrapper over canonical P7.02/P7.06 runtime/service path
- Uses existing `launchctl bootstrap/kickstart` with label `com.arvectum.os.persistent-internal`
- Atomic mkdir lock prevents duplicate startup
- All system paths are absolute (Finder-compatible)
- No shell profile dependency
- Generated `.app` is not tracked in git
