export const MENU_IDS = Object.freeze({
  root: "sort-tabs",
  host: "sort-tabs-host",
  title: "sort-tabs-title",
});

export async function registerMenus(menus) {
  await menus.removeAll();
  // menus.create returns an ID, not a Promise. Its callback reports errors.
  const create = properties => new Promise((resolve, reject) => {
    menus.create(properties, () => {
      const error = globalThis.browser?.runtime.lastError;
      if (error) reject(new Error(error.message));
      else resolve();
    });
  });
  await create({ id: MENU_IDS.root, title: "Sort Tabs", contexts: ["tab"] });
  for (const [mode, title] of [["host", "By Host"], ["title", "By Title"]]) {
    await create({ id: MENU_IDS[mode], parentId: MENU_IDS.root, title, contexts: ["tab"] });
  }
}

export function createMenuHandler(enqueueSort, reportError) {
  return (info, tab) => {
    const mode = info.menuItemId === MENU_IDS.host ? "host"
      : info.menuItemId === MENU_IDS.title ? "title" : null;
    if (!mode || !Number.isInteger(tab?.windowId)) return;
    return enqueueSort(tab.windowId, mode).catch(reportError);
  };
}
