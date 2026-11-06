/**
 * Give visually colliding fitted categories distinct labels without rewriting values.
 * The exact original string must stay in <option value> and the Predict payload.
 */
export function predictionCategoryChoices(options: readonly string[]): {value: string; label: string}[] {
  const valuesByVisibleLabel = new Map<string, Set<string>>();
  for (const value of options) {
    const visible = value.trim();
    const values = valuesByVisibleLabel.get(visible) ?? new Set<string>();
    values.add(value);
    valuesByVisibleLabel.set(visible, values);
  }

  // Names for frequent invisible boundary characters; a Unicode code point
  // is shown for every other whitespace to avoid merging distinct raw inputs.
  const whitespaceName = (char: string): string => {
    const names: Record<string, string> = {
      ' ': 'SPACE', '\t': 'TAB', '\n': 'LINE FEED', '\r': 'CARRIAGE RETURN',
      '\u00a0': 'NO-BREAK SPACE'
    };
    return names[char] ?? `U+${char.codePointAt(0)!.toString(16).toUpperCase().padStart(4, '0')}`;
  };
  const codepoints = (value: string): string => Array.from(value, whitespaceName).join(' + ');

  return options.map(value => {
    const visible = value.trim();
    if ((valuesByVisibleLabel.get(visible)?.size ?? 0) < 2) {
      return {value, label: value};
    }
    if (value.length === 0) return {value, label: '(blank category) (empty raw value)'};
    if (visible.length === 0) {
      return {value, label: `(blank category) (whitespace: ${codepoints(value)})`};
    }

    const leading = value.slice(0, value.length - value.trimStart().length);
    const trailing = value.slice(value.trimEnd().length);
    const details: string[] = [];
    if (leading) details.push(`leading: ${codepoints(leading)}`);
    if (trailing) details.push(`trailing: ${codepoints(trailing)}`);
    if (!details.length) details.push('exact value');
    return {value, label: `${visible} (${details.join('; ')})`};
  });
}
