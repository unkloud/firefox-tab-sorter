import test from "node:test";
import assert from "node:assert/strict";
import { compareTabs, hostKey, sortedTabs, titleKey } from "../extension/sorting.js";
import { tabs, ids } from "./helpers.js";

test("title sort is case-insensitive and natural, and preserves equal-key order", () => {
  const input = tabs(["Page 10", "page 2", "Apple", "apple", "Page 1"]);
  assert.deepEqual(ids(sortedTabs(input, "title")), [3, 4, 5, 2, 1]);
});

test("host sort ignores scheme, port and path, then compares titles naturally", () => {
  const input = tabs([
    { url: "https://B.test/", title: "A" },
    { url: "https://a.test/path", title: "Page 10" },
    { url: "http://a.test:8080/another", title: "Page 2" },
    { url: "https://a.test/", title: "page 2" },
    { url: "https://blog.a.test/", title: "A" },
  ]);
  assert.deepEqual(ids(sortedTabs(input, "host")), [3, 4, 2, 1, 5]);
  assert.equal(hostKey({ url: "https://WWW.Example.test:8443/path" }), "www.example.test");
});

test("hostless and malformed URLs follow hosted tabs and sort by title", () => {
  const input = tabs([
    { url: "about:config", title: "Settings" },
    { url: "not a URL", title: "Broken" },
    { url: "file:///tmp/a.html", title: "File" },
    { url: "https://z.test/", title: "Z" },
    { url: "about:blank", title: "Blank" },
  ]);
  assert.deepEqual(ids(sortedTabs(input, "host")), [4, 5, 2, 3, 1]);
  assert.equal(hostKey({}), "");
});

test("untitled tabs fall back to URL, with safe handling of missing metadata", () => {
  assert.equal(titleKey({ title: "  ", url: "https://example.test/" }), "https://example.test/");
  assert.equal(titleKey({ title: "  A title  " }), "A title");
  assert.equal(titleKey({}), "");
  assert.deepEqual(ids(sortedTabs(tabs([
    { title: "", url: "https://b.test/" },
    { title: undefined, url: "https://a.test/" },
  ]), "title")), [2, 1]);
});

test("pinned tabs stay fixed and keep their relative order", () => {
  assert.deepEqual(ids(sortedTabs(tabs([
    { title: "Z", pinned: true }, { title: "A", pinned: true }, "D", "B", "C",
  ]), "title")), [1, 2, 4, 5, 3]);
});

test("groups sort internally; ungrouped gaps never exchange tabs", () => {
  const input = tabs([
    "Z", "Y", { title: "D", groupId: 8 }, { title: "C", groupId: 8 },
    "B", "A", { title: "G", groupId: 9 }, { title: "F", groupId: 9 }, "E",
  ]);
  assert.deepEqual(ids(sortedTabs(input, "title")), [2, 1, 4, 3, 6, 5, 8, 7, 9]);
});

test("hidden tabs and split-view pairs are fixed boundaries, including inside groups", () => {
  const input = tabs([
    "Z", "Y", { title: "X", hidden: true }, "W", "V",
    { title: "U", splitViewId: 0 }, { title: "T", splitViewId: 0 },
    { title: "S", groupId: 1 }, { title: "R", groupId: 1 },
    { title: "Q", groupId: 1, hidden: true },
    { title: "P", groupId: 1 }, { title: "O", groupId: 1 },
  ]);
  assert.deepEqual(ids(sortedTabs(input, "title")), [2, 1, 3, 5, 4, 6, 7, 9, 8, 10, 12, 11]);
});

test("empty, single and all-fixed windows are unchanged", () => {
  for (const input of [[], tabs(["A"]), tabs([{ pinned: true }, { hidden: true }])]) {
    assert.deepEqual(sortedTabs(input, "title"), input);
  }
});

test("planning does not mutate input and uses tab-strip order for stable ties", () => {
  const input = tabs(["same", "SAME", "Same"]).reverse();
  const before = structuredClone(input);
  assert.deepEqual(ids(sortedTabs(input, "title")), [1, 2, 3]);
  assert.deepEqual(input, before);
});

test("older tab records without group/split fields can be sorted", () => {
  const input = tabs(["Z", "A"]);
  for (const tab of input) { delete tab.groupId; delete tab.splitViewId; }
  assert.deepEqual(ids(sortedTabs(input, "title")), [2, 1]);
});

test("unknown sort modes fail rather than silently selecting a default", () => {
  assert.throws(() => compareTabs("url"), TypeError);
});
