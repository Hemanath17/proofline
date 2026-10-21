import { describe, expect, it, beforeEach } from "vitest";
import { isTypingTarget, shortcutsEnabled, setShortcutsEnabled } from "@/components/KeyboardLayer";

function elementWithTag(tag: string): HTMLElement {
  return document.createElement(tag);
}

describe("isTypingTarget", () => {
  it("is true for INPUT, TEXTAREA, SELECT and contentEditable elements", () => {
    expect(isTypingTarget(elementWithTag("input"))).toBe(true);
    expect(isTypingTarget(elementWithTag("textarea"))).toBe(true);
    expect(isTypingTarget(elementWithTag("select"))).toBe(true);

    const editable = document.createElement("div");
    // jsdom doesn't compute `isContentEditable` from the `contentEditable`
    // attribute the way a real browser does, so it's stubbed directly here
    // to exercise the same branch a real editable element would hit.
    Object.defineProperty(editable, "isContentEditable", { value: true, configurable: true });
    expect(isTypingTarget(editable)).toBe(true);
  });

  it("is false for a plain element, null, or a non-element target", () => {
    expect(isTypingTarget(elementWithTag("button"))).toBe(false);
    expect(isTypingTarget(elementWithTag("div"))).toBe(false);
    expect(isTypingTarget(null)).toBe(false);
    expect(isTypingTarget(window)).toBe(false);
  });
});

describe("shortcutsEnabled / setShortcutsEnabled", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("defaults to enabled, and persists the WCAG 2.1.4 off switch", () => {
    expect(shortcutsEnabled()).toBe(true);
    setShortcutsEnabled(false);
    expect(shortcutsEnabled()).toBe(false);
    setShortcutsEnabled(true);
    expect(shortcutsEnabled()).toBe(true);
  });
});
