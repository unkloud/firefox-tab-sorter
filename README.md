# Tab Sorter

A small Firefox desktop extension that adds **Sort Tabs → By Host / By Title** to the menu shown when you right-click a tab. Requires Firefox 140 or newer. There is no toolbar button or settings page.

## Build instructions for Mozilla reviewers

This source submission is for **Tab Sorter 1.0.0** (`tab_sorter-1.0.0.zip`). All shipped source files are in `extension/`. The add-on contains original, readable JavaScript, JSON, and SVG. There is no transpilation, concatenation, minification, or build-time code generation, and there are no third-party runtime libraries. The only build operation is to package the files without changing their bytes.

### Build environment and prerequisites

- **Operating system:** Linux. The reviewer build was verified on Linux x86_64 with Python 3.12.3. Packaging uses only the Python standard library, with no CPU-specific compilation or tools.
- **Required program:** Python **3.12 or newer**. On Ubuntu 24.04, install the distribution's Python 3.12 with `sudo apt-get update` followed by `sudo apt-get install python3`. Check the version using `python3 --version`.
- **Node.js, npm, web-ext, Git, and Firefox are not needed to rebuild this source submission.** They are used only by the optional development and browser-testing workflows documented below. The original uploaded ZIP was packaged with web-ext 10.8.0; the reviewer script reproduces the same extension file contents using Python.
- **Network access:** None after Python is installed and this source ZIP is extracted. Do not run `npm ci` or download the browser compatibility matrix to rebuild the add-on.

### Step-by-step build

1. Extract the source ZIP to a directory, then open a terminal in that directory (the directory containing this README, `extension/`, and `scripts/`).
2. Run `python3 --version` and confirm version 3.12 or newer.
3. Run the complete build script:

   ```sh
   python3 scripts/build-reviewer.py
   ```

4. Find the rebuilt add-on at `dist/tab_sorter-1.0.0-rebuilt.zip`.
5. To verify it against the submitted **unsigned extension ZIP**, run:

   ```sh
   python3 scripts/build-reviewer.py --compare /path/to/tab_sorter-1.0.0.zip
   ```

The comparison checks the complete set of files and every byte in each file, including the manifest and icon. It fails if any file is missing, added, or changed. ZIP compression, timestamps, and directory-only entries may differ from the original web-ext archive; the unpacked add-on code and resources are identical. The Python-built ZIP itself has fixed metadata and is reproducible. Compare against the unsigned upload, because Mozilla adds signing files afterward.

Only `extension/` is included in the installable add-on. This source submission also includes the build script, tests, development package/lock files, license, and documentation; these are not shipped as runtime extension files. The standard npm build remains available in the Development section for maintainers.

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
git clone https://github.com/unkloud/firefox-tab-sorter.git
cd firefox-tab-sorter
npm ci
npm test
npm run lint
npm run build
npm start
```

`npm start` launches Firefox with a separate development profile and reloads the extension when its files change. `npm run build` packages only `extension/` into `dist/tab_sorter-1.0.0.zip`; tests and development dependencies are excluded. No compilation step or runtime dependencies are needed. Unit tests can also run without installing dependencies:

```sh
node --test test/*.test.js
```

`web-ext` 10.8.0 also checks Android's minimum version and emits one Android-only warning about the no-data-collection declaration. This manifest targets desktop Firefox only (no `gecko_android` entry); that declaration is supported by desktop Firefox 140. The warning is retained in lint output rather than expanding the extension's platform support to silence it.

The implementation separates pure comparison/section planning (`extension/sorting.js`), guarded sequential moves and per-window queues (`extension/sort-window.js`), and menu registration/dispatch (`extension/menus.js` and `extension/background.js`).

## Browser checks

The retained [compatibility report](compatibility/results.md) records each tested stable release from Firefox 140.0 through 160.0.1, including point releases. It identifies the exact extension and test-suite hashes. This is a Linux x86_64, en-US, headless browser matrix; ESR, beta, developer edition, nightly, Android, Windows and macOS are not included.

All 63 pinned releases passed on 21 November 2026, using the initial packaged extension. That report predates the display-name correction to **Tab Sorter**; its recorded package hash identifies the tested build. The renamed package passed targeted browser checks on Firefox 140.0 and 160.0.1. Earlier offline reruns passed on 140.0 and 149.0. The 32 extension unit tests and 10 matrix-runner regression tests also passed.

The automated smoke test needs Python 3 and an installed Firefox. Run `python3 scripts/firefox-smoke.py` (optionally `--firefox /path/to/firefox` or `--extension dist/tab_sorter-1.0.0.zip`). It starts a disposable headless profile and a loopback-only fixture server, invokes the actual tab context menu, and cleans up afterward. Browser UI access is enabled only for that test process; your normal Firefox profile is not used.

### Run the release matrix locally

Requirements: Linux x86_64, Python 3.12+, `curl`, and Firefox's usual system libraries. The first complete run downloads several GB from Mozilla's official archive. Every browser archive is checked against Mozilla's SHA-512 checksum before extraction. Browsers are cached in `.firefox-cache/`, with automatic updates disabled; each test uses a new temporary profile.

```sh
npm run build
npm run test:compat:unit
npm run test:compat -- --extension dist/tab_sorter-1.0.0.zip --jobs 3
```

The version list is pinned in `compatibility/releases.json`. The runner writes `compatibility/results.json` and a readable `compatibility/results.md` after each completed release. It exits nonzero if a requested release fails or has no build for this platform. Detailed per-version results, harness output, and Firefox logs remain in `compatibility/logs/`. Browser downloads and logs are excluded from Git; the suite, version list, and complete report are retained in Git.

Both native menu commands, title/host ordering, groups and ungrouped gaps, pinned and hidden boundaries, active tabs, containers, a second window, and repeat-sort idempotence are tested on every version. Split-view preservation is additionally tested from Firefox 149, when the extension API exposes split-view membership. Earlier releases explicitly report that one check as unavailable; their core tests must still pass. Each test also verifies that Firefox is running the exact requested version.

Useful reruns:

```sh
# Rerun every version from cached downloads, without network access.
npm run test:compat -- --extension dist/tab_sorter-1.0.0.zip --offline

# Retry an interrupted run; reuse passes only for the same extension and suite.
npm run test:compat -- --extension dist/tab_sorter-1.0.0.zip --resume

# Test a subset; its default report goes under logs/ to preserve the full report.
npm run test:compat -- --versions 140.0,149.0,160.0.1 --offline

# Explicitly refresh the stable version list from Mozilla, then exit.
npm run test:compat -- --discover --minimum 140.0 --maximum 160.0.1
```

Omitting `--extension` tests the source `extension/` directory. Use the same ZIP when resuming a package run; source and ZIP hashes are deliberately different. Removing `.firefox-cache/` frees the browser downloads, and the next online run recreates them. Node tests remain available through `npm test`; the Python matrix regression tests cover release discovery, checksum validation, archive extraction, offline handling, resume rules, and incomplete reporting.

### Additional manual scenarios

Use a separate Firefox profile with two windows. Open tabs with mixed hosts/titles, duplicate titles, numeric titles, and internal pages. Add pinned tabs, groups, hidden tabs where available, and a split view where supported. Run both context-menu commands and check:

- Correct ordering within each eligible section; repeated sorting makes no further changes.
- Pinned/hidden/split tabs and group positions stay fixed; group membership and container assignments survive.
- The active tab stays active and the other window is unchanged.
- Closing a tab or changing a group during a sort stops remaining work without unhandled errors; a subsequent command succeeds.
- The menu survives restarting Firefox with the extension installed, and reloading a temporary installation does not duplicate menu entries.

## Repository

Source, tests, and compatibility results are available at [unkloud/firefox-tab-sorter](https://github.com/unkloud/firefox-tab-sorter). Browser downloads, detailed test logs, build artifacts, and development dependencies are excluded from Git.

## License

[MIT](LICENSE) — copyright (c) 2026 unkloud.
