"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useRef } from "react";
import { type Language, message, translateText } from "@/lib/i18n";

type I18nContextValue = {
  language: Language;
  locale: "en-RW" | "rw-RW";
  t: (key: string, fallback?: string) => string;
  text: (value: string) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);
const originalText = new WeakMap<Text, string>();
const lastRenderedText = new WeakMap<Text, string>();
const originalAttributes = new WeakMap<Element, Map<string, string>>();
const translatedAttributes = ["placeholder", "title", "aria-label"] as const;

function translateNode(node: Node, language: Language) {
  if (node.nodeType === Node.TEXT_NODE) {
    const textNode = node as Text;
    const parent = textNode.parentElement;
    if (!parent || ["SCRIPT", "STYLE", "TEXTAREA", "CODE", "PRE"].includes(parent.tagName)) return;
    const current = textNode.nodeValue ?? "";
    let source = originalText.get(textNode);
    if (source === undefined) {
      source = current;
      originalText.set(textNode, source);
      // Preserve option values: translated labels must not change submitted values.
      if (parent.tagName === "OPTION" && !parent.hasAttribute("value")) parent.setAttribute("value", source.trim());
    } else if (current !== source && current !== lastRenderedText.get(textNode)) {
      // React replaced the text with fresh source content (for example a new API reading).
      source = current;
      originalText.set(textNode, source);
    }
    const next = translateText(source, language);
    lastRenderedText.set(textNode, next);
    if (current !== next) textNode.nodeValue = next;
    return;
  }

  if (!(node instanceof Element)) return;
  const stored = originalAttributes.get(node) ?? new Map<string, string>();
  for (const attribute of translatedAttributes) {
    const current = node.getAttribute(attribute);
    if (current === null) continue;
    if (!stored.has(attribute)) stored.set(attribute, current);
    const next = translateText(stored.get(attribute) ?? current, language);
    if (current !== next) node.setAttribute(attribute, next);
  }
  originalAttributes.set(node, stored);
  for (const child of Array.from(node.childNodes)) translateNode(child, language);
}

export default function I18nProvider({ language, children }: { language: Language; children: ReactNode }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const context = useMemo<I18nContextValue>(() => ({
    language,
    locale: language === "rw" ? "rw-RW" : "en-RW",
    t: (key, fallback) => message(language, key, fallback),
    text: (value) => translateText(value, language),
  }), [language]);

  useEffect(() => {
    document.documentElement.lang = language === "rw" ? "rw" : "en";
    const nativeAlert = window.alert;
    const nativeConfirm = window.confirm;
    window.alert = (value?: unknown) => nativeAlert.call(window, translateText(String(value ?? ""), language));
    window.confirm = (value?: string) => nativeConfirm.call(window, translateText(String(value ?? ""), language));
    const root = rootRef.current;
    if (!root) {
      window.alert = nativeAlert;
      window.confirm = nativeConfirm;
      return;
    }
    if (language === "en") root.querySelectorAll("input, select, textarea").forEach((item) => (item as HTMLInputElement).setCustomValidity(""));
    const validate = (event: Event) => {
      const control = event.target as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
      if (typeof control.setCustomValidity !== "function") return;
      control.setCustomValidity(language === "rw" ? message(language, control.validity.valueMissing ? "validation.required" : "validation.invalid") : "");
    };
    const clearValidation = (event: Event) => {
      const control = event.target as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
      if (typeof control.setCustomValidity === "function") control.setCustomValidity("");
    };
    root.addEventListener("invalid", validate, true);
    root.addEventListener("input", clearValidation, true);
    translateNode(root, language);
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === "characterData") translateNode(mutation.target, language);
        for (const added of Array.from(mutation.addedNodes)) translateNode(added, language);
      }
    });
    observer.observe(root, { childList: true, characterData: true, subtree: true });
    return () => {
      observer.disconnect();
      root.removeEventListener("invalid", validate, true);
      root.removeEventListener("input", clearValidation, true);
      window.alert = nativeAlert;
      window.confirm = nativeConfirm;
    };
  }, [language]);

  return <I18nContext.Provider value={context}><div ref={rootRef} className="min-h-screen" lang={language === "rw" ? "rw" : "en"} data-language={language}>{children}</div></I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) throw new Error("useI18n must be used inside I18nProvider");
  return context;
}
