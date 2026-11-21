// Runs only in the disposable test profile's privileged Marionette context.
const port = arguments[0];
const done = arguments[arguments.length - 1];
(async () => {
  const win = Services.wm.getMostRecentWindow("navigator:browser");
  const g = win.gBrowser;
  const major = Number.parseInt(Services.appinfo.version, 10);
  const hasSplitViews = major >= 149;
  const skipped = hasSplitViews ? [] : ["Split-view preservation: WebExtensions splitViewId is available from Firefox 149"];
  const check = (condition, message) => { if (!condition) throw new Error(message); };
  const pause = ms => new Promise(resolve => win.setTimeout(resolve, ms));
  const waitFor = async (predicate, message) => {
    for (let attempt = 0; attempt < 150; attempt++) {
      if (predicate()) return;
      await pause(50);
    }
    throw new Error(typeof message === "function" ? message() : message);
  };
  const createTab = (title, host = "a.localhost", options = {}) => {
    const tab = g.addTab(`http://${host}:${port}/${encodeURIComponent(title)}`, {
      triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
      ...options,
    });
    tab.setAttribute("smoke-title", title);
    return tab;
  };
  const original = [...g.tabs];
  const pinned = createTab("Pinned");
  const z = createTab("Page 10", "a.localhost", { userContextId: 1 });
  const a = createTab("Page 2", "z.localhost");
  const groupZ = createTab("Group Z", "a.localhost");
  const groupA = createTab("Group A", "z.localhost");
  const gapZ = createTab("Gap Z", "a.localhost");
  const gapA = createTab("Gap A", "z.localhost");
  const hidden = createTab("Hidden");
  const splitZ = hasSplitViews ? createTab("Split Z") : null;
  const splitA = hasSplitViews ? createTab("Split A") : null;
  const tailZ = createTab("Tail Z", "a.localhost");
  const tailA = createTab("Tail A", "z.localhost");
  const fixtures = [pinned, z, a, groupZ, groupA, gapZ, gapA, hidden, splitZ, splitA, tailZ, tailA].filter(Boolean);
  g.selectedTab = z;
  for (const tab of original) g.removeTab(tab);
  await waitFor(() => fixtures.every(tab => tab.label === tab.getAttribute("smoke-title")), "Fixture pages did not load");
  g.pinTab(pinned);
  const group = g.addTabGroup([groupZ, groupA], { label: "Smoke group", color: "blue", insertBefore: gapZ });
  g.hideTab(hidden);
  const split = hasSplitViews ? g.addTabSplitView([splitZ, splitA], { insertBefore: tailZ }) : null;
  g.selectedTab = z;
  const ids = () => [...g.tabs].map(tab => tab.getAttribute("smoke-title"));
  const splitTitles = hasSplitViews ? ["Split Z", "Split A"] : [];
  const expectedTitle = ["Pinned", "Page 2", "Page 10", "Group A", "Group Z", "Gap A", "Gap Z", "Hidden", ...splitTitles, "Tail A", "Tail Z"];
  const expectedHost = ["Pinned", "Page 10", "Page 2", "Group Z", "Group A", "Gap Z", "Gap A", "Hidden", ...splitTitles, "Tail Z", "Tail A"];
  const initialGroup = group.id;
  const selected = g.selectedTab;
  const container = z.userContextId;
  const checks = [];
  const other = win.OpenBrowserWindow();
  await waitFor(() => other.gBrowserInit?.delayedStartupFinished, "Second window did not open");
  other.gBrowser.addTab("about:config", { triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal() });
  const otherSnapshot = [...other.gBrowser.tabs];
  win.focus();

  async function invokeMenu(label) {
    const popup = win.document.getElementById("tabContextMenu");
    // Open the actual native tab context menu, then dispatch its real command.
    const event = new win.MouseEvent("contextmenu", { bubbles: true, cancelable: true, button: 2 });
    a.dispatchEvent(event);
    if (popup.state === "closed") popup.openPopup(a, "after_start", 0, 0, true, false, event);
    await waitFor(() => [...popup.querySelectorAll("menu")].some(item => item.getAttribute("label") === "Sort Tabs"), "Sort Tabs menu missing");
    const root = [...popup.querySelectorAll("menu")].find(item => item.getAttribute("label") === "Sort Tabs");
    const item = [...root.querySelectorAll("menuitem")].find(node => node.getAttribute("label") === label);
    check(item, `${label} menu item missing`);
    check(root.querySelectorAll("menuitem").length === 2, "Unexpected menu entries");
    item.doCommand();
    popup.hidePopup();
  }

  await invokeMenu("By Title");
  await waitFor(() => JSON.stringify(ids()) === JSON.stringify(expectedTitle), () => `Title order wrong: ${JSON.stringify(ids())}`);
  checks.push("Native By Title menu: natural sorting, groups and ungrouped gaps");
  check(g.selectedTab === selected, "Active tab changed");
  check(z.userContextId === container, "Container changed");
  check(group.id === initialGroup && groupA.group === group && groupZ.group === group, "Group membership changed");
  check(pinned.pinned && [...g.tabs].indexOf(hidden) === 7 && hidden.hidden, "Pinned/hidden tabs changed");
  if (hasSplitViews) {
    check(splitZ.splitview === split && splitA.splitview === split && split.tabs[0] === splitZ, "Split view changed");
    checks.push("Split view preserved");
  }
  checks.push("Active tab, container, pinned tab, hidden boundary and group membership preserved");

  await invokeMenu("By Host");
  await waitFor(() => JSON.stringify(ids()) === JSON.stringify(expectedHost), () => `Host order wrong: ${JSON.stringify(ids())}`);
  checks.push("Native By Host menu: hostname sorting in each section");
  let moveCount = 0;
  const onMove = () => { moveCount++; };
  g.tabContainer.addEventListener("TabMove", onMove);
  await invokeMenu("By Host");
  await pause(400);
  g.tabContainer.removeEventListener("TabMove", onMove);
  check(moveCount === 0, "Repeated sort moved tabs");
  checks.push("Repeated sort is a no-op");
  check([...other.gBrowser.tabs].every((tab, index) => tab === otherSnapshot[index]) && other.gBrowser.tabs.length === otherSnapshot.length, "Other window changed");
  checks.push("Second window untouched");
  other.close();
  return { ok: true, checks, skipped, order: ids() };
})().then(done, error => done({
  ok: false, error: String(error), stack: error.stack,
  console: Services.console.getMessageArray().map(item => item.message)
    .filter(message => /Tab Sorter|firefox-tab-sorter|moz-extension/.test(message)),
}));
