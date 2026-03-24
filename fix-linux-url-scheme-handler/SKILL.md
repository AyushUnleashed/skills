---
name: fix-linux-url-scheme-handler
description: >
  Diagnoses and fixes broken URL scheme / protocol handler registrations on Ubuntu/Linux,
  so that custom app URLs like cursor://, vscode://, slack://, spotify://, discord://,
  notion://, obsidian://, figma://, etc. correctly open the right desktop app instead of
  failing silently, opening a blank window, or treating the URL as a file path.

  Use this skill whenever a user reports any of these symptoms:
  - "clicking Approve in OAuth doesn't do anything"
  - "xdg-open can't find the app"
  - "the URL opens as a new file in my editor"
  - "the browser shows 'open app' but nothing happens"
  - "MCP server / OAuth callback isn't working on Linux"
  - "deep link not working on Ubuntu"
  - any app that worked on macOS/Windows but protocol URLs fail on Linux
---

# Fix Linux URL Scheme Handler

When a website or browser tries to open a custom URL like `cursor://...` or `slack://...`,
the OS uses `xdg-open` to find and launch the right app. Two things must be true for this
to work:

1. The app's `.desktop` file declares it handles the scheme (`MimeType=x-scheme-handler/<scheme>;`)
2. The scheme is registered to point at that `.desktop` file

If either is missing or stale, the URL silently fails, opens nothing, or (for Electron apps)
gets treated as a file path to open in the editor.

---

## Step 1 — Identify the scheme and app

Ask the user (or infer from context):
- What is the URL scheme? (e.g. `cursor`, `vscode`, `slack`, `discord`, `spotify`)
- What app should handle it?

---

## Step 2 — Check what's currently registered

```bash
xdg-mime query default x-scheme-handler/<scheme>
```

Possible outcomes:
- **Returns nothing** → scheme is not registered at all
- **Returns `some-nonexistent.desktop`** → registered but the file doesn't exist (stale/broken)
- **Returns the correct `.desktop` file** → registration is fine; skip to Step 4 to check the Exec line

---

## Step 3 — Find the app's .desktop file

```bash
find /usr/share/applications ~/.local/share/applications -iname "*<appname>*" 2>/dev/null
```

Common locations:
- System-wide: `/usr/share/applications/<app>.desktop`
- User-local: `~/.local/share/applications/<app>.desktop`
- AppImage installs often create `~/.local/share/applications/<app>.desktop`

Read the file once found.

---

## Step 4 — Add MimeType if missing

If the `.desktop` file does not contain `MimeType=x-scheme-handler/<scheme>;`, add it.
Append to the end of the `[Desktop Entry]` block:

```ini
MimeType=x-scheme-handler/<scheme>;
```

If a `MimeType=` line already exists, append the new entry to it (semicolon-separated):

```ini
MimeType=x-scheme-handler/existing;x-scheme-handler/<scheme>;
```

---

## Step 5 — Fix the Exec line for URL handling

This is the most common silent failure. Check the `Exec=` line:

**Wrong (URL treated as a file to open):**
```ini
Exec=/path/to/app --some-flags %U
```

**For Electron-based apps** (Cursor, VS Code, VSCodium, Windsurf, Zed, and any app built
on Electron/Chromium), the app won't process `cursor://...` as a deep link unless told to.
Add `--open-url` before `%U`:

```ini
Exec=/path/to/app --no-sandbox --open-url %U
```

**For non-Electron apps** (Slack native, Discord, Spotify, Obsidian AppImage, etc.),
just `%U` is typically correct — but verify the app isn't creating a blank file. If it is,
check the app's own CLI flags (`--url`, `--deeplink`, etc.).

**How to tell if an app is Electron-based:** It uses Chromium under the hood. VS Code,
Cursor, Windsurf, Zed, Slack (desktop), Discord, Obsidian, and Notion are all Electron apps.
A quick tell: the binary accepts `--inspect` or `--remote-debugging-port` flags.

---

## Step 6 — Register the handler

```bash
xdg-mime default <app>.desktop x-scheme-handler/<scheme>
```

Use just the filename (not the full path) of the `.desktop` file.

---

## Step 7 — Refresh the MIME database

```bash
update-desktop-database ~/.local/share/applications/
```

If the `.desktop` file is in `/usr/share/applications/`, also run:
```bash
sudo update-desktop-database /usr/share/applications/
```

---

## Step 8 — Verify

```bash
xdg-mime query default x-scheme-handler/<scheme>
```

Should return the correct `.desktop` filename. Then ask the user to retry the OAuth / deep
link flow.

---

## Common app reference

| App | Scheme | Electron? | Exec flag needed |
|-----|--------|-----------|-----------------|
| Cursor | `cursor` | Yes | `--open-url %U` |
| VS Code | `vscode` | Yes | `--open-url %U` |
| VSCodium | `vscodium` | Yes | `--open-url %U` |
| Windsurf | `windsurf` | Yes | `--open-url %U` |
| Slack | `slack` | Yes | `--open-url %U` |
| Discord | `discord` | Yes | `--open-url %U` |
| Obsidian | `obsidian` | Yes | `--open-url %U` |
| Notion | `notion` | Yes | `--open-url %U` |
| Spotify | `spotify` | No | `%U` |
| Zoom | `zoommtg` / `zoomus` | No | `%U` |
| 1Password | `onepassword` | No | `%U` |

---

## Diagnostic summary (if unsure where the break is)

Run all of these and share the output:

```bash
# 1. What's registered?
xdg-mime query default x-scheme-handler/<scheme>

# 2. Does that .desktop file actually exist?
find /usr/share/applications ~/.local/share/applications -name "$(xdg-mime query default x-scheme-handler/<scheme>)" 2>/dev/null

# 3. What does the Exec line look like?
grep -i "exec\|mimetype" ~/.local/share/applications/<app>.desktop 2>/dev/null || grep -i "exec\|mimetype" /usr/share/applications/<app>.desktop 2>/dev/null
```
