// SPDX-License-Identifier: AGPL-3.0-or-later
// The classes of editor.module.css, typed.
import css from "./editor.module.css";

export const editorStyles = css as Record<
  | "bar"
  | "editor"
  | "group"
  | "letter"
  | "noColor"
  | "page"
  | "paper"
  | "picker"
  | "ribbon"
  | "select"
  | "size"
  | "swatch"
  | "swatches"
  | "title"
  | "titleHelp"
  | "tool",
  string
>;
