# Mozilla Add-ons listing images

Upload `icon-128.png` in the listing's **Images → Add-on icon** field. It is a PNG export of the extension's existing SVG icon, with transparent rounded corners. The 32, 64, and 512 pixel versions are also included for reuse; only one icon upload is needed.

Mozilla recommends a square 128 × 128 PNG or JPEG [listing icon](https://mozilla.github.io/addons-server/topics/api/addons/#addon-icon) and 1280 × 800 [listing screenshots](https://extensionworkshop.com/documentation/develop/create-an-appealing-listing/). The screenshots here are 1280 × 800 PNGs.

Upload the screenshots in this order, using these captions:

| File | Caption |
| --- | --- |
| `01-sort-menu.png` | Right-click a tab and choose Sort Tabs → By Host or By Title. |
| `02-by-title.png` | Sort page titles naturally: Page 2 comes before Page 10. The active tab stays active. |
| `03-by-host.png` | Sort by website hostname, then by page title within each hostname. |

The screenshots were captured in Firefox 160.0.1 on Linux with the actual extension loaded in a disposable profile. The pages are locally served demonstration content, not extension UI. The native menu commands were invoked and the resulting tab order and active tab checked before capture. The host example uses atlas.localhost, birch.localhost, and cedar.localhost.

These are listing assets only. They do not change the extension package or require a new extension version. The vector icon source remains `extension/icons/sort-tabs.svg`.
