# Firefox compatibility results

63 passed; 0 failed; 0 builds unavailable; 0 pending.

Platform: Linux x86_64, en-US, headless; regular stable releases (including point releases).
ESR, beta, developer edition, nightly, Android, Windows and macOS are outside this matrix.

Run started (UTC): 2026-11-21T07:05:34.812326+00:00
Extension SHA-256: `c37aa0b803147e4bd0284c8775c59e514ea18f5690408475a64fea984066d46d`
Suite SHA-256: `5939af4df44234e2a48f130947daff94310630bcb5723c4bd039630c01bf7bd9`

Both native sorting menu commands, natural ordering, group and gap boundaries, pinned/hidden tabs,
active tab and container preservation, window isolation, and repeat-sort idempotence are checked.
Split-view preservation is additionally checked from Firefox 149; earlier versions explicitly skip only that feature.

| Firefox | Result | Split views | Notes |
| --- | --- | --- | --- |
| 140.0 | pass | not available |  |
| 140.0.1 | pass | not available |  |
| 140.0.2 | pass | not available |  |
| 140.0.4 | pass | not available |  |
| 141.0 | pass | not available |  |
| 141.0.2 | pass | not available |  |
| 141.0.3 | pass | not available |  |
| 142.0 | pass | not available |  |
| 142.0.1 | pass | not available |  |
| 143.0 | pass | not available |  |
| 143.0.1 | pass | not available |  |
| 143.0.3 | pass | not available |  |
| 143.0.4 | pass | not available |  |
| 144.0 | pass | not available |  |
| 144.0.2 | pass | not available |  |
| 145.0 | pass | not available |  |
| 145.0.1 | pass | not available |  |
| 145.0.2 | pass | not available |  |
| 146.0 | pass | not available |  |
| 146.0.1 | pass | not available |  |
| 147.0 | pass | not available |  |
| 147.0.1 | pass | not available |  |
| 147.0.2 | pass | not available |  |
| 147.0.3 | pass | not available |  |
| 147.0.4 | pass | not available |  |
| 148.0 | pass | not available |  |
| 148.0.2 | pass | not available |  |
| 149.0 | pass | checked |  |
| 149.0.2 | pass | checked |  |
| 150.0 | pass | checked |  |
| 150.0.1 | pass | checked |  |
| 150.0.2 | pass | checked |  |
| 150.0.3 | pass | checked |  |
| 151.0 | pass | checked |  |
| 151.0.1 | pass | checked |  |
| 151.0.2 | pass | checked |  |
| 151.0.3 | pass | checked |  |
| 151.0.4 | pass | checked |  |
| 152.0 | pass | checked |  |
| 152.0.1 | pass | checked |  |
| 152.0.2 | pass | checked |  |
| 152.0.3 | pass | checked |  |
| 152.0.4 | pass | checked |  |
| 152.0.5 | pass | checked |  |
| 152.0.6 | pass | checked |  |
| 153.0 | pass | checked |  |
| 153.0.1 | pass | checked |  |
| 153.0.3 | pass | checked |  |
| 153.0.4 | pass | checked |  |
| 154.0 | pass | checked |  |
| 154.0.1 | pass | checked |  |
| 155.0 | pass | checked |  |
| 155.0.1 | pass | checked |  |
| 156.0 | pass | checked |  |
| 156.0.1 | pass | checked |  |
| 157.0 | pass | checked |  |
| 157.0.1 | pass | checked |  |
| 158.0 | pass | checked |  |
| 158.0.1 | pass | checked |  |
| 159.0 | pass | checked |  |
| 159.0.1 | pass | checked |  |
| 160.0 | pass | checked |  |
| 160.0.1 | pass | checked |  |

Browsers come from [Mozilla's release archive](https://archive.mozilla.org/pub/firefox/releases/)
and are checked against the release's SHA512SUMS before extraction. Browser caches and detailed logs remain local and are ignored by Git.
