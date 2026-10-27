/** Distinguish visually identical categorical choices without altering fitted-model inputs. */
export function predictionCategoryChoices(options: readonly string[]): {value: string; label: string}[] {
  const rawValuesByVisibleLabel = new Map<string, Set<string>>();
  for (const value of options) {
    const visible = value.trim();
    const raw = rawValuesByVisibleLabel.get(visible) ?? new Set<string>();
    raw.add(value);
    rawValuesByVisibleLabel.set(visible, raw);
  }

  return options.map(value => {
    const visible = value.trim();
    if ((rawValuesByVisibleLabel.get(visible)?.size ?? 0) < 2) {
      return {value, label: value};
    }

    const leading = value.length - value.trimStart().length;
    const trailing = value.length - value.trimEnd().length;
    const details: string[] = [];
    if (visible.length === 0) {
      details.push(`${value.length} whitespace character${value.length === 1 ? '' : 's'}`);
    } else {
      if (leading > 0) details.push(`${leading} leading whitespace character${leading === 1 ? '' : 's'}`);
      if (trailing > 0) details.push(`${trailing} trailing whitespace character${trailing === 1 ? '' : 's'}`);
      if (!details.length) details.push('exact value');
    }
    return {value, label: `${visible || '(blank category)'} (${details.join(', ')})`};
  });
}
