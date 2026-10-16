// SPDX-License-Identifier: AGPL-3.0-or-later
// The classes of watch.module.css, typed, so that a misspelt class is a type error.
import emptyCss from "../EmptyPage.module.css";
import css from "./watch.module.css";

export const styles = css as Record<
  "article"
  | "badge"
  | "blocked"
  | "button"
  | "card"
  | "danger"
  | "error"
  | "field"
  | "filter"
  | "form"
  | "good"
  | "help"
  | "journal"
  | "limited"
  | "list"
  | "meta"
  | "neutral"
  | "notice"
  | "panel"
  | "primary"
  | "row"
  | "success"
  | "tab"
  | "tabs"
  | "text"
  | "warning",
  string
>;
export const emptyStyles = emptyCss as Record<"empty" | "headline" | "next" | "page", string>;
