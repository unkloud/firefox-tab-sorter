import { sortedTabs } from "./sorting.js";

export class SortInterrupted extends Error {
  constructor() {
    super("Tabs changed during sorting. Run the command again to finish.");
    this.name = "SortInterrupted";
  }
}

function snapshot(tabs) {
  return [...tabs].sort((a, b) => a.index - b.index);
}

function sameLayout(actual, expected) {
  return actual.length === expected.length && actual.every((tab, index) => {
    const other = expected[index];
    return tab.id === other.id && tab.index === index &&
      tab.windowId === other.windowId &&
      Boolean(tab.pinned) === Boolean(other.pinned) &&
      Boolean(tab.hidden) === Boolean(other.hidden) &&
      (tab.groupId ?? -1) === (other.groupId ?? -1) &&
      (tab.splitViewId ?? -1) === (other.splitViewId ?? -1) &&
      tab.cookieStoreId === other.cookieStoreId &&
      tab.title === other.title && tab.url === other.url;
  });
}

/** Apply moves from left to right, entirely inside the planner's boundaries. */
export async function sortWindow(tabsApi, windowId, mode) {
  let expected = snapshot(await tabsApi.query({ windowId }));
  const desired = sortedTabs(expected, mode);
  let moved = 0;

  for (let index = 0; index < desired.length; index++) {
    const id = desired[index].id;
    if (expected[index].id === id) continue;

    const current = snapshot(await tabsApi.query({ windowId }));
    if (!sameLayout(current, expected)) throw new SortInterrupted();

    // Omit windowId: sorting must never deliberately transfer a tab to a window.
    // Moving a later tab left keeps every intervening tab in the same run/group.
    await tabsApi.move(id, { index });
    const from = expected.findIndex(tab => tab.id === id);
    const [tab] = expected.splice(from, 1);
    expected.splice(index, 0, tab);
    expected = expected.map((item, position) => ({ ...item, index: position }));
    moved++;

    // Verify even the final move; an API may silently decline a move.
    const actual = snapshot(await tabsApi.query({ windowId }));
    if (!sameLayout(actual, expected)) throw new SortInterrupted();
  }
  return { moved };
}

/** A rejected operation must not block the next command for that window. */
export function createWindowSorter(tabsApi) {
  const pending = new Map();
  return function enqueueSort(windowId, mode) {
    const previous = pending.get(windowId) ?? Promise.resolve();
    const operation = previous.catch(() => {}).then(() => sortWindow(tabsApi, windowId, mode));
    pending.set(windowId, operation);
    const cleanUp = () => {
      if (pending.get(windowId) === operation) pending.delete(windowId);
    };
    operation.then(cleanUp, cleanUp);
    return operation;
  };
}
