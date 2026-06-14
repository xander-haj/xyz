/*
  Small progressive enhancements for the Z3R wiki. The page remains readable
  without JavaScript, while this file adds navigation state, tabs, search, and copy buttons.
*/

const ACTIVE_CLASS = "is-active";
const HIDDEN_CLASS = "is-hidden";

/**
 * Finds all matching elements under the provided root.
 * Parameters:
 *   selector: CSS selector string to query.
 *   root: parent node to search from; defaults to the full document.
 * Returns: a real Array so callers can use array helpers safely.
 */
function selectAll(selector, root = document) {
  return Array.from(root.querySelectorAll(selector));
}

/**
 * Adds copy buttons to command blocks so setup commands are easier to reuse.
 * Parameters: none.
 * Returns: nothing; mutates the DOM by inserting button elements.
 */
function enhanceCodeBlocks() {
  selectAll("pre").forEach((block) => {
    const code = block.querySelector("code");

    // A copy button only makes sense when the block contains actual command or path text.
    if (!code || !code.textContent.trim()) {
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = "Copy";
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(code.textContent.trim());
        button.textContent = "Copied";
        window.setTimeout(() => {
          button.textContent = "Copy";
        }, 1400);
      } catch {
        button.textContent = "Select";
      }
    });
    block.appendChild(button);
  });
}

/**
 * Connects each tab list to its panels.
 * Parameters: none.
 * Returns: nothing; updates ARIA-selected-like visual state and visible panel classes.
 */
function connectTabs() {
  selectAll("[data-tabs]").forEach((tabGroup) => {
    const buttons = selectAll("[data-tab]", tabGroup);
    const panels = selectAll("[data-panel]", tabGroup);

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.tab;

        // Only one platform panel should be visible so readers do not compare mixed commands by accident.
        buttons.forEach((item) => item.classList.toggle(ACTIVE_CLASS, item === button));
        panels.forEach((panel) => {
          panel.classList.toggle(ACTIVE_CLASS, panel.dataset.panel === target);
        });
      });
    });
  });
}

/**
 * Filters documentation sections by heading, body text, or explicit search tags.
 * Parameters: none.
 * Returns: nothing; toggles the hidden class on unmatched sections.
 */
function connectSearch() {
  const input = document.querySelector("#wiki-search");
  const sections = selectAll(".doc-section");

  // The page is fully browsable without the search input, so missing markup simply disables this enhancement.
  if (!input) {
    return;
  }

  input.addEventListener("input", () => {
    const query = input.value.trim().toLowerCase();

    sections.forEach((section) => {
      const searchableText = [
        section.dataset.tags || "",
        section.textContent,
      ].join(" ").toLowerCase();
      section.classList.toggle(HIDDEN_CLASS, Boolean(query) && !searchableText.includes(query));
    });
  });
}

/**
 * Highlights the sidebar item for the section closest to the top of the viewport.
 * Parameters: none.
 * Returns: nothing; observes section visibility and updates navigation classes.
 */
function connectActiveNav() {
  const links = selectAll(".sidebar-nav a");
  const sections = selectAll(".doc-section");

  // IntersectionObserver keeps scroll handling efficient on longer documentation pages.
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) {
        return;
      }

      const sectionHash = `#${entry.target.id}`;
      const activeLink = links.find((link) => link.getAttribute("href") === sectionHash);
      links.forEach((link) => link.classList.toggle(ACTIVE_CLASS, link === activeLink));
    });
  }, { rootMargin: "-20% 0px -70% 0px" });

  sections.forEach((section) => observer.observe(section));
}

/**
 * Initializes every optional wiki behavior after the DOM is ready.
 * Parameters: none.
 * Returns: nothing.
 */
function initWiki() {
  enhanceCodeBlocks();
  connectTabs();
  connectSearch();
  connectActiveNav();
}

document.addEventListener("DOMContentLoaded", initWiki);
