const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "accent",
});

export function titleKey(tab) {
  return tab.title?.trim() || tab.url?.trim() || "";
}

export function hostKey(tab) {
  try {
    return new URL(tab.url).hostname.toLowerCase();
  } catch {
    return "";
  }
}

export function compareTabs(mode) {
  if (mode !== "host" && mode !== "title") {
    throw new TypeError(`Unknown sort mode: ${mode}`);
  }
  return (left, right) => {
    if (mode === "host") {
      const a = hostKey(left);
      const b = hostKey(right);
      // Internal pages and malformed URLs follow tabs with a hostname.
      if (Boolean(a) !== Boolean(b)) return a ? -1 : 1;
      const byHost = collator.compare(a, b);
      if (byHost) return byHost;
    }
    return collator.compare(titleKey(left), titleKey(right));
  };
}

export function groupId(tab) {
  return tab.groupId ?? -1;
}

export function isBoundary(tab) {
  return tab.pinned || tab.hidden || (tab.splitViewId ?? -1) !== -1;
}

/** Return an ordered copy; neither tabs nor the input array are modified. */
export function sortedTabs(tabs, mode) {
  const compare = compareTabs(mode);
  const ordered = [...tabs].sort((a, b) => a.index - b.index);
  const result = [];
  let run = [];
  function flush() {
    // Array.sort is stable: equal keys retain the original tab-strip order.
    result.push(...run.sort(compare));
    run = [];
  }
  for (const tab of ordered) {
    if (isBoundary(tab)) {
      flush();
      result.push(tab);
    } else {
      if (run.length && groupId(run[0]) !== groupId(tab)) flush();
      run.push(tab);
    }
  }
  flush();
  return result;
}
