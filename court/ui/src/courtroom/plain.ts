// Plain words for the room: claims and outputs without CSS selectors, percentages from 0..1 scores.

const words = (id: string) => id.replace(/[-_]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase();

/** 'Typing into #item and clicking #add (the + button)' -> 'Typing into “item” and clicking “add” (the + button)'. */
export function plainClaim(text: string): string {
  return text
    .replace(/(^|[\s(])[#.]([a-zA-Z][\w-]*)(?:\s+(?:li|ul|ol|div|span|button|input|a|p)\b)?/g, (_, pre: string, id: string) => `${pre}“${words(id)}”`)
    .replace(/\s{2,}/g, ' ')
    .trim();
}

/** 0.89 -> '89%', 89 -> '89%', missing -> null. */
export function pct(x: number | null | undefined): string | null {
  if (typeof x !== 'number' || !Number.isFinite(x)) return null;
  return `${Math.round(x <= 1 ? x * 100 : x)}%`;
}
