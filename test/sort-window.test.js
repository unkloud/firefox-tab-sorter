import test from "node:test";
import assert from "node:assert/strict";
import { createWindowSorter, sortWindow, SortInterrupted } from "../extension/sort-window.js";
import { tabs, fakeTabs, ids } from "./helpers.js";

test("sort moves only target-window tabs and preserves tab identity and state", async () => {
  const initial = tabs([
    { title: "Pinned", pinned: true },
    { title: "C", active: true, cookieStoreId: "firefox-container-2" },
    { title: "B", active: false }, { title: "A", active: false },
  ]);
  const otherWindow = tabs([{ id: 20, title: "Z" }, { id: 21, title: "A" }], 2);
  const { state, api } = fakeTabs([...initial, ...otherWindow]);
  assert.deepEqual(await sortWindow(api, 1, "title"), { moved: 2 });
  assert.deepEqual(ids(state.tabs), [1, 4, 3, 2, 20, 21]);
  for (const original of [...initial, ...otherWindow]) {
    const actual = state.tabs.find(tab => tab.id === original.id);
    assert.deepEqual({ ...actual, index: original.index }, original);
  }
  assert.ok(state.moves.every(move => !Object.hasOwn(move, "windowId")));
  assert.deepEqual(await sortWindow(api, 1, "title"), { moved: 0 });
});

test("moves preserve grouped/ungrouped sections, hidden tabs and split views", async () => {
  const { state, api } = fakeTabs(tabs([
    "Z", "Y", { title: "D", groupId: 7 }, { title: "C", groupId: 7 },
    { title: "H", hidden: true }, "B", "A",
    { title: "F", splitViewId: 1 }, { title: "E", splitViewId: 1 }, "J", "I",
  ]));
  await sortWindow(api, 1, "title");
  assert.deepEqual(ids(state.tabs), [2, 1, 4, 3, 5, 7, 6, 8, 9, 11, 10]);
  assert.deepEqual(state.moves.map(move => move.id), [2, 4, 7, 11]);
});

test("a tab closing before the first move aborts without moving anything", async () => {
  const { state, api } = fakeTabs(tabs(["C", "B", "A"]));
  state.beforeQuery = count => { if (count === 2) state.tabs.pop(); };
  await assert.rejects(sortWindow(api, 1, "title"), SortInterrupted);
  assert.equal(state.moves.length, 0);
});

for (const [description, mutate] of [
  ["closing", state => state.tabs.pop()],
  ["opening", state => state.tabs.push({ ...state.tabs[0], id: 90, index: 3 })],
  ["pinning", state => { state.tabs[1].pinned = true; }],
  ["grouping", state => { state.tabs[1].groupId = 9; }],
  ["hiding", state => { state.tabs[1].hidden = true; }],
  ["splitting", state => { state.tabs[1].splitViewId = 0; }],
  ["navigation", state => { state.tabs[1].url = "https://changed.test/"; }],
  ["title changes", state => { state.tabs[1].title = "Changed"; }],
  ["detaching", state => { state.tabs[1].windowId = 2; }],
  ["manual reordering", state => {
    [state.tabs[1], state.tabs[2]] = [state.tabs[2], state.tabs[1]];
    state.tabs.forEach((tab, index) => { tab.index = index; });
  }],
]) {
  test(`${description} during a sort stops the remaining moves`, async () => {
    const { state, api } = fakeTabs(tabs(["C", "B", "A"]));
    state.afterMove = () => mutate(state);
    await assert.rejects(sortWindow(api, 1, "title"), SortInterrupted);
    assert.equal(state.moves.length, 1);
  });
}

test("a silently declined move is detected, including on the final move", async () => {
  const { api } = fakeTabs(tabs(["B", "A"]));
  api.move = async () => [];
  await assert.rejects(sortWindow(api, 1, "title"), SortInterrupted);
});

test("browser failures propagate without retrying stale moves", async () => {
  const { state, api } = fakeTabs(tabs(["B", "A"]));
  api.move = async () => { throw new Error("Window closed"); };
  await assert.rejects(sortWindow(api, 1, "title"), /Window closed/);
  assert.equal(state.moves.length, 0);
});

test("commands for the same window serialize and take fresh snapshots", async () => {
  const { state, api } = fakeTabs(tabs([
    { title: "A", url: "https://c.test/" },
    { title: "B", url: "https://b.test/" },
    { title: "C", url: "https://a.test/" },
  ]));
  let resolveFirstMove;
  const barrier = new Promise(resolve => { resolveFirstMove = resolve; });
  let moved;
  const firstMove = new Promise(resolve => { moved = resolve; });
  state.afterMove = async count => { if (count === 1) { moved(); await barrier; } };
  const sort = createWindowSorter(api);
  const host = sort(1, "host");
  await firstMove;
  const title = sort(1, "title");
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(state.moves.length, 1);
  resolveFirstMove();
  await Promise.all([host, title]);
  assert.deepEqual(ids(state.tabs), [1, 2, 3]);
});

test("a failed command does not poison the per-window queue", async () => {
  const { state, api } = fakeTabs(tabs(["B", "A"]));
  const sort = createWindowSorter(api);
  const invalid = sort(1, "invalid");
  const valid = sort(1, "title");
  await assert.rejects(invalid, TypeError);
  await valid;
  assert.deepEqual(ids(state.tabs), [2, 1]);
});

test("a busy window does not block sorting a different window", async () => {
  const { state, api } = fakeTabs([
    ...tabs(["B", "A"]), ...tabs([{ id: 3, title: "D" }, { id: 4, title: "C" }], 2),
  ]);
  const originalQuery = api.query;
  let release;
  const barrier = new Promise(resolve => { release = resolve; });
  api.query = async query => {
    if (query.windowId === 1) await barrier;
    return originalQuery(query);
  };
  const sort = createWindowSorter(api);
  const blocked = sort(1, "title");
  await sort(2, "title");
  assert.deepEqual(ids(state.tabs.filter(tab => tab.windowId === 2)), [4, 3]);
  release();
  await blocked;
});
