/** Represent invisible whitespace in an exact, read-only Quality change preview. */
export function qualityPreviewLabel(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value !== 'string') return String(value);
  if (value === '') return '(empty string)';

  const whitespaceNames: Record<string, string> = {
    ' ': 'SPACE',
    '\t': 'TAB',
    '\n': 'LINE FEED',
    '\r': 'CARRIAGE RETURN',
    '\u00a0': 'NO-BREAK SPACE',
  };
  const visible = Array.from(value, character => {
    const named = whitespaceNames[character];
    if (named) return `[${named}]`;
    if (/\s/u.test(character)) {
      const codepoint = character.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0');
      return `[U+${codepoint}]`;
    }
    return character;
  }).join('');
  return `"${visible}"`;
}
