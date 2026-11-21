export function tabs(specifications, windowId = 1) {
  return specifications.map((spec, index) => ({
    id: index + 1, index, windowId,
    url: "https://example.test/", title: "", pinned: false, hidden: false,
    groupId: -1, splitViewId: -1, active: index === 0,
    cookieStoreId: "firefox-default",
    ...(typeof spec === "string" ? { title: spec } : spec),
  }));
}

export function fakeTabs(initial) {
  const state = { tabs: structuredClone(initial), moves: [], queries: 0 };
  const api = {
    async query({ windowId }) {
      state.queries++;
      await state.beforeQuery?.(state.queries);
      return structuredClone(state.tabs.filter(tab => tab.windowId === windowId));
    },
    async move(id, properties) {
      const tab = state.tabs.find(item => item.id === id);
      if (!tab) throw new Error("Tab closed");
      const windowTabs = state.tabs.filter(item => item.windowId === tab.windowId)
        .sort((a, b) => a.index - b.index);
      windowTabs.splice(windowTabs.indexOf(tab), 1);
      windowTabs.splice(properties.index, 0, tab);
      windowTabs.forEach((item, index) => { item.index = index; });
      state.tabs.sort((a, b) => a.windowId - b.windowId || a.index - b.index);
      state.moves.push({ id, ...properties });
      await state.afterMove?.(state.moves.length);
      return structuredClone(tab);
    },
  };
  return { state, api };
}

export function ids(items) { return items.map(tab => tab.id); }
