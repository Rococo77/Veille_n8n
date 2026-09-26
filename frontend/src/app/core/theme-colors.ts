/**
 * Teintes proposées par défaut : chacune garde au moins 3:1 de contraste sur le fond clair
 * (#f2f4f6) et sur le fond sombre (#101419), donc reste visible dans les deux modes.
 */
export const THEME_PALETTE = [
  '#c05621',
  '#2b8a8a',
  '#8b5cf6',
  '#d6336c',
  '#3b8f3b',
  '#1f7fbf',
  '#a16207',
  '#0e7490',
] as const;

const PAPER_LIGHT = '#f2f4f6';
const PAPER_DARK = '#101419';
export const MIN_THEME_CONTRAST = 3;

function linear(hexPair: string): number {
  const c = parseInt(hexPair, 16) / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  return (
    0.2126 * linear(hex.slice(1, 3)) +
    0.7152 * linear(hex.slice(3, 5)) +
    0.0722 * linear(hex.slice(5, 7))
  );
}

export function contrast(a: string, b: string): number {
  const la = luminance(a);
  const lb = luminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Contraste le plus faible entre la couleur et les deux fonds de l'application. */
export function worstContrast(hex: string): number {
  return Math.min(contrast(hex, PAPER_LIGHT), contrast(hex, PAPER_DARK));
}

export function isReadableThemeColor(hex: string): boolean {
  return worstContrast(hex) >= MIN_THEME_CONTRAST;
}

/** Première teinte de la palette encore inutilisée, pour que deux thèmes ne se confondent pas. */
export function nextThemeColor(used: readonly string[]): string {
  const taken = new Set(used.map((c) => c.toLowerCase()));
  const free = THEME_PALETTE.find((c) => !taken.has(c));
  if (free) return free;
  // Palette épuisée : on recommence le cycle plutôt que de retomber sur la couleur d'accent.
  return THEME_PALETTE.at(used.length % THEME_PALETTE.length) ?? THEME_PALETTE[0];
}
