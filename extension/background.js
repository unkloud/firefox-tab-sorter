import { createWindowSorter, SortInterrupted } from "./sort-window.js";
import { createMenuHandler, registerMenus } from "./menus.js";

const enqueueSort = createWindowSorter(browser.tabs);
function reportError(error) {
  // Do not include tab titles, URLs, or raw browser error messages in logs.
  console.warn(error instanceof SortInterrupted
    ? "Tab Sorter: tabs changed during sorting; run the command again to finish."
    : "Tab Sorter: sorting could not finish; run the command again.");
}

// Register event listeners synchronously so Firefox can wake the MV3 event page.
browser.menus.onClicked.addListener(createMenuHandler(enqueueSort, reportError));
browser.runtime.onInstalled.addListener(() => registerMenus(browser.menus).catch(reportError));
browser.runtime.onStartup.addListener(() => registerMenus(browser.menus).catch(reportError));
