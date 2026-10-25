// SPDX-License-Identifier: AGPL-3.0-or-later
// « Rechercher » in a draft or an article (Joël, 2026-10-24): every occurrence marked, in the
// draft and, when comparing, in the reference beside it; « suivant » and « précédent » go
// through them in the order of the page. The marks are CSS highlights over the text shown:
// nothing is written into the document, in the editor neither. Ctrl+F opens it.
import { useEffect, useRef, useState, type RefObject } from "react";
import { useTranslation } from "react-i18next";
import { styles } from "../watch/styles.ts";

const ALL = "otlet-search";
const CURRENT = "otlet-search-current";

/** The occurrences of `query` in the text under `root`, in the order of the page; case aside. */
function occurrences(root: Node, query: string): Range[] {
  const wanted = query.trim().toLocaleLowerCase();
  if (wanted === "") {
    return [];
  }
  const found: Range[] = [];
  // The text read, not the controls around it: buttons, lists, labels.
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      node.parentElement?.closest("select, option, button, label, input, textarea, [role=search]")
        ? NodeFilter.FILTER_REJECT
        : NodeFilter.FILTER_ACCEPT,
  });
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    const text = (node.textContent ?? "").toLocaleLowerCase();
    for (let at = text.indexOf(wanted); at >= 0; at = text.indexOf(wanted, at + wanted.length)) {
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + wanted.length);
      found.push(range);
    }
  }
  return found;
}

function paint(name: string, ranges: Range[]): void {
  if (typeof CSS === "undefined" || !("highlights" in CSS)) {
    return; // an older browser: the count and the scrolling still work
  }
  if (ranges.length === 0) {
    CSS.highlights.delete(name);
  } else {
    CSS.highlights.set(name, new Highlight(...ranges));
  }
}

export function TextSearch({ within }: { within: RefObject<HTMLElement | null> }) {
  const { t } = useTranslation();
  const input = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [found, setFound] = useState<Range[]>([]);
  const [current, setCurrent] = useState(0);

  // Ctrl+F (⌘F) opens the search of Otlet; pressed again in it, the browser's own.
  useEffect(() => {
    const open = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f" && document.activeElement !== input.current) {
        event.preventDefault();
        input.current?.focus();
        input.current?.select();
      }
    };
    window.addEventListener("keydown", open);
    return () => {
      window.removeEventListener("keydown", open);
    };
  }, []);

  // Searched again when the text changes: typing in the editor, another version, Comparer.
  useEffect(() => {
    const root = within.current;
    if (root === null) {
      return;
    }
    let timer = 0;
    const search = () => {
      const ranges = occurrences(root, query);
      setFound(ranges);
      setCurrent((before) => (before < ranges.length ? before : 0));
      paint(ALL, ranges);
    };
    search();
    const observer = new MutationObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(search, 150);
    });
    observer.observe(root, { subtree: true, childList: true, characterData: true });
    return () => {
      observer.disconnect();
      window.clearTimeout(timer);
      paint(ALL, []);
      paint(CURRENT, []);
    };
  }, [within, query]);

  useEffect(() => {
    const range = found[current];
    paint(CURRENT, range === undefined ? [] : [range]);
  }, [found, current]);

  const go = (step: number) => {
    if (found.length === 0) {
      return;
    }
    const next = (current + step + found.length) % found.length;
    setCurrent(next);
    found[next]?.startContainer.parentElement?.scrollIntoView({ block: "center", behavior: "smooth" });
  };

  return (
    <p className={styles.row} role="search">
      <label htmlFor="text-search" className="visually-hidden">
        {t("textSearch.label")}
      </label>
      <input
        id="text-search"
        ref={input}
        type="search"
        placeholder={t("textSearch.placeholder")}
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setCurrent(0);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            go(event.shiftKey ? -1 : 1);
          } else if (event.key === "Escape") {
            setQuery("");
          }
        }}
      />
      <button type="button" className={styles.button} disabled={found.length === 0} aria-label={t("textSearch.previous")} onClick={() => { go(-1); }}>
        ↑
      </button>
      <button type="button" className={styles.button} disabled={found.length === 0} aria-label={t("textSearch.next")} onClick={() => { go(1); }}>
        ↓
      </button>
      {query.trim() !== "" && (
        <span className={styles.meta} aria-live="polite">
          {found.length === 0 ? t("textSearch.none") : t("textSearch.count", { current: current + 1, count: found.length })}
        </span>
      )}
    </p>
  );
}
