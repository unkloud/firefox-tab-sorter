import test from "node:test";
import assert from "node:assert/strict";
import { createMenuHandler, MENU_IDS, registerMenus } from "../extension/menus.js";

test("registers only the tab-context submenu and its two sorting commands", async () => {
  let items = [{ id: "old" }];
  const menus = {
    async removeAll() { items = []; },
    create(properties, callback) { items.push(properties); callback(); return properties.id; },
  };
  await registerMenus(menus);
  await registerMenus(menus);
  assert.deepEqual(items, [
    { id: MENU_IDS.root, title: "Sort Tabs", contexts: ["tab"] },
    { id: MENU_IDS.host, parentId: MENU_IDS.root, title: "By Host", contexts: ["tab"] },
    { id: MENU_IDS.title, parentId: MENU_IDS.root, title: "By Title", contexts: ["tab"] },
  ]);
});

test("both menu commands use the clicked tab's window", async () => {
  const calls = [];
  const handle = createMenuHandler(async (...args) => calls.push(args), assert.fail);
  await handle({ menuItemId: MENU_IDS.host }, { windowId: 7 });
  await handle({ menuItemId: MENU_IDS.title }, { windowId: 8 });
  await handle({ menuItemId: MENU_IDS.root }, { windowId: 1 });
  await handle({ menuItemId: "unrelated" }, { windowId: 1 });
  await handle({ menuItemId: MENU_IDS.host });
  assert.deepEqual(calls, [[7, "host"], [8, "title"]]);
});

test("menu command failures are handled instead of becoming unhandled rejections", async () => {
  const errors = [];
  const error = new Error("Interrupted");
  const handle = createMenuHandler(async () => { throw error; }, item => errors.push(item));
  await handle({ menuItemId: MENU_IDS.title }, { windowId: 1 });
  assert.deepEqual(errors, [error]);
});
