const THEME_KEY = "mosaic_theme"; // "light" | "dark" | null (follow system)

export function systemPrefersDark() {
  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches ?? false;
}

export function readStoredTheme() {
  return localStorage.getItem(THEME_KEY);
}

export function resolveTheme(stored) {
  if (stored === "light" || stored === "dark") return stored;
  return systemPrefersDark() ? "dark" : "light";
}

export function applyTheme(mode) {
  document.documentElement.dataset.theme = mode;
}

export function persistTheme(mode) {
  localStorage.setItem(THEME_KEY, mode);
  applyTheme(mode);
}
