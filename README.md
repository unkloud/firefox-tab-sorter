# Firefox Tab Sorter

A small Firefox desktop extension that adds **Sort Tabs → By Host / By Title** to the menu shown when you right-click a tab. Requires Firefox 140 or newer. There is no toolbar button or settings page.

## Install temporarily

1. Open `about:debugging#/runtime/this-firefox` in Firefox.
2. Choose **Load Temporary Add-on…**.
3. Select `extension/manifest.json` in this repository, or the ZIP in `dist/` after building.
4. Right-click any tab, open **Sort Tabs**, and choose **By Host** or **By Title**.

Firefox removes temporary add-ons when it exits. The ZIP is unsigned; permanent installation in standard Firefox requires Mozilla signing. This project does not publish or sign the extension automatically. See [Mozilla's distribution guide](https://extensionworkshop.com/documentation/publish/signing-and-distribution-overview/).

## Sorting rules

- Only the clicked tab's window is sorted, regardless of which tabs are selected.
- Sort order is ascending, case-insensitive, and natural: `Page 2` precedes `Page 10`. Alphabetical ordering follows the browser locale.
- **By Host** compares the full hostname, ignoring scheme, port, and path. Subdomains, including `www`, remain distinct. Equal hosts are ordered by title; pages without a hostname (such as `about:blank` and local files) follow hosted pages and are ordered by title.
- **By Title** uses the page title, falling back to its URL when the title is empty. Equal keys keep their original order.
- Pinned tabs stay in place. Each group sorts internally and keeps its position and membership. Each contiguous ungrouped section sorts separately.
- Hidden tabs and split-view tabs stay in place and divide the tabs into separate sortable sections. This also applies within a group.
- Sorting moves existing tabs; it does not activate, reload, close, duplicate, or change their containers.

Commands for the same window run in order. If tabs are opened, closed, moved, regrouped, or change title/URL during sorting, remaining moves stop when the change is detected. Moves already completed stay in place; run the command again once the tabs settle. Firefox has no atomic tab-reordering API, so a user action can occur between a layout check and a move. Failures are reported in the extension's console, available through **Inspect** in `about:debugging`.

## Privacy and permissions

All processing is local and transient. The extension has no content scripts, network requests, storage, analytics, or telemetry.

- `tabs`: read titles/URLs across the current window to calculate the order.
- `menus`: add the two commands to the tab context menu.

The manifest declares that no data is collected. Private windows work only if you separately allow the extension to run in private browsing through Firefox's add-on settings.

## Development

Install Node.js 22 or newer with npm, then run:

```sh
npm ci
npm test
npm run lint
npm run build
npm start
```

`npm start` launches Firefox with a separate development profile and reloads the extension when its files change. `npm run build` packages only `extension/` into `dist/firefox_tab_sorter-1.0.0.zip`; tests and development dependencies are excluded. No compilation step or runtime dependencies are needed. Unit tests can also run without installing dependencies:

```sh
node --test test/*.test.js
```

`web-ext` 10.8.0 also checks Android's minimum version and emits one Android-only warning about the no-data-collection declaration. This manifest targets desktop Firefox only (no `gecko_android` entry); that declaration is supported by desktop Firefox 140. The warning is retained in lint output rather than expanding the extension's platform support to silence it.

The implementation separates pure comparison/section planning (`extension/sorting.js`), guarded sequential moves and per-window queues (`extension/sort-window.js`), and menu registration/dispatch (`extension/menus.js` and `extension/background.js`).

## Browser checks

Validated on Firefox 160.0.1: both native menu commands, natural title ordering, sorting within groups and gaps, fixed pinned/hidden/split-view tabs, active tab and container preservation, a second untouched window, and repeated-sort idempotence. The smoke test passed for both the source directory and the packaged ZIP. All 32 unit tests pass; source and ZIP validation report zero errors and the Android-only warning described above.

The automated smoke test needs Python 3 and an installed Firefox. Run `python3 scripts/firefox-smoke.py` (optionally `--firefox /path/to/firefox` or `--extension dist/firefox_tab_sorter-1.0.0.zip`). It starts a disposable headless profile and a loopback-only fixture server, invokes the actual tab context menu, and cleans up afterward. Browser UI access is enabled only for that test process; your normal Firefox profile is not used.

Use a separate Firefox profile with two windows. Open tabs with mixed hosts/titles, duplicate titles, numeric titles, and internal pages. Add pinned tabs, groups, hidden tabs where available, and a split view where supported. Run both context-menu commands and check:

- Correct ordering within each eligible section; repeated sorting makes no further changes.
- Pinned/hidden/split tabs and group positions stay fixed; group membership and container assignments survive.
- The active tab stays active and the other window is unchanged.
- Closing a tab or changing a group during a sort stops remaining work without unhandled errors; a subsequent command succeeds.
- The menu survives restarting Firefox with the extension installed, and reloading a temporary installation does not duplicate menu entries.

## Repository

This directory is a standalone Git repository with its own history. It is locally excluded from the parent `Tools` repository, and has no remote configured.
