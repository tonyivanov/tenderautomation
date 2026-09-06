export function parseRuPublishedAt(text: string): Date | undefined {
  // Expected examples:
  // "Опубликован 09.04.2026, 13:37"
  // "Опубликован 09.04.2026"
  // "Опубликован: 09.04.2026, 13:37"
  const m = text.match(/(\d{2})\.(\d{2})\.(\d{4})(?:\s*,\s*(\d{2}):(\d{2}))?/);
  if (!m) return undefined;
  const dd = Number(m[1]);
  const mm = Number(m[2]);
  const yyyy = Number(m[3]);
  const hh = m[4] ? Number(m[4]) : 0;
  const mi = m[5] ? Number(m[5]) : 0;
  if (![dd, mm, yyyy, hh, mi].every(Number.isFinite)) return undefined;
  // Interpret in local timezone.
  return new Date(yyyy, mm - 1, dd, hh, mi, 0, 0);
}

export function toIso(d?: Date): string | undefined {
  return d ? d.toISOString() : undefined;
}

