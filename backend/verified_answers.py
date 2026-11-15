"""Read-only answers to supported Ask ODIN questions on a working version."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
import re
from typing import Literal

import pandas as pd

try:
    from . import analytics, explore_filters, storage
except ImportError:
    import analytics, explore_filters, storage


OVERVIEW = re.compile(r'(?:what is the dataset overview|dataset overview|give me (?:a|the) dataset overview|report the dataset dimensions and quality counts)')
MISSING_CAUSE = re.compile(
    r'(?:(?:why (?:are values missing|is data missing) (?:in|from)|missing count and cause for)\s+(.+?)'
    r'|why (?:are|is) (.+?) missing)', re.I)
LABEL_RATE = re.compile(r'(?:what is the )?(?:labelled |labeled )?positive rate for ("[^"\r\n]+")\s*=\s*("[^"\r\n]+")', re.I)
TRAINING = re.compile(r'(?:training status|has training started(?: for this dataset)?|report whether training started and the validation score)')
MOST_MISSING = re.compile(r'which (.+?) (?:have|has) (?:the )?most missing (.+)', re.I)
COMPARE_MISSING = re.compile(r'(?:count|show|compare) missing (?:values (?:in|for) )?(.+)', re.I)
MISSING_OVERVIEW = re.compile(r'(?:which columns have missing values(?: and why does it matter)?|show missing values by column)')
RATE = (
    re.compile(r'(?:what )?(?:percentage|percent|proportion|share) of (labelled|labeled) (.+?) (?:are|is|equal) (.+)', re.I),
    re.compile(r'(?:what )?(?:percentage|percent|proportion|share) of all (?:rows|records) (?:have|has|with) (?:an? )?(.+)', re.I),
)
AMBIGUOUS_RATE = re.compile(r'(?:what )?(?:percentage|percent|proportion|share) of (.+?) (?:are|is|equal) (.+)', re.I)
SUMMARY = re.compile(r'(?:(?:what is (?:the )?)|(?:calculate|show|give me) (?:the )?)?'
                     r'(median|mean|average|sum|total|min|minimum|max|maximum) (?:of )?(.+)', re.I)
COUNT = re.compile(r'(?:how many |count (?:the )?)(?:rows|records) (?:are there )?'
                   r'(?:where|with|for) (.+)', re.I)
FOLLOW_UP = re.compile(r'(?:what about|how about|and for) (.+)', re.I)
FIELD_TOKEN = r'(?:"[^"\r\n]+"|[^"])+?'
CONDITION = re.compile(rf'({FIELD_TOKEN})\s*(?:=|\bis\b|\bequals\b)\s*(.+)', re.I)
AGGREGATIONS = {'average': 'mean', 'total': 'sum', 'minimum': 'min', 'maximum': 'max'}


class AnalysisQuestion(ValueError):
    """The question needs clarification or exceeds the supported scope."""


@dataclass(frozen=True)
class AnalysisPlan:
    operation: str
    measure: str | None = None
    group_by: str | None = None
    filter_column: str | None = None
    filter_value: str | None = None
    denominator: Literal['labelled', 'all_rows'] | None = None


@dataclass(frozen=True)
class FollowUp:
    project_id: str
    dataset_version: int
    question: str


def _key(value: str) -> str:
    return re.sub(r"[\W_]+", " ", value.casefold()).strip()


def _variants(key: str) -> set[str]:
    values = {key} if key else set()
    if key.endswith('s') and len(key) > 2 and not key.endswith(('ss', 'us', 'is')):
        values.add(key[:-1])
    if key.endswith('ies') and len(key) > 3:
        values.add(key[:-3] + 'y')
    if key.endswith(('ses', 'xes', 'zes', 'ches', 'shes')):
        values.add(key[:-2])
    return values


def _is_quoted(value: str) -> bool:
    return len(value) > 2 and value.startswith('"') and value.endswith('"') and value.count('"') == 2


def _field(frame: pd.DataFrame, phrase: str) -> str:
    phrase = phrase.strip()
    if _is_quoted(phrase):
        name = phrase[1:-1]
        if name in frame:
            return name
        options = []
    elif '"' in phrase:
        options = []
    else:
        variants = _variants(_key(phrase))
        options = [name for name in frame if _variants(_key(name)) & variants]
        if not options:
            options = [name for name in frame if any(
                key.endswith(' ' + variant)
                for key in _variants(_key(name)) for variant in variants)]
    if len(options) == 1:
        return options[0]
    if options:
        choices = ', '.join(repr(name) for name in options[:6])
        raise AnalysisQuestion(f'Which column do you mean by {phrase!r}? Possible columns include {choices}. Use the exact column name in double quotes.')
    raise AnalysisQuestion(f'Use an existing column name in double quotes. I could not find the column {phrase!r}.')


def _label_mask(series: pd.Series, label: str) -> tuple[str, pd.Series]:
    label = label.strip()
    if _is_quoted(label):
        resolved = label[1:-1]
        mask = explore_filters.label_matches(series, resolved)
    elif '"' not in label:
        mask = explore_filters.label_matches(series, label, exact=False)
        options = series.loc[mask].astype(str).unique()
        if len(options) != 1:
            raise AnalysisQuestion('Use an observed value, with the exact spelling in double quotes. The value may be absent or ambiguous.')
        resolved = options[0]
    else:
        raise AnalysisQuestion('Use an observed value in double quotes.')
    if not mask.any():
        raise AnalysisQuestion('Use an observed positive label or filter value, with the exact spelling shown in the dataset.')
    return resolved, mask


def _split_phrase(phrase: str, separator: str) -> tuple[str, str] | None:
    # Keep separators inside quoted column names and labels literal.
    match = re.fullmatch(rf'({FIELD_TOKEN})\s+(?:{separator})\s+(.+)', phrase, re.I)
    return (match[1], match[2]) if match else None


def _filter(frame: pd.DataFrame, phrase: str) -> tuple[str, str]:
    match = CONDITION.fullmatch(phrase)
    if match:
        return _field(frame, match[1]), match[2]
    # Also accept ordinary wording such as Yes outcomes or "In review" statuses.
    match = re.fullmatch(r'("[^"\r\n]+"|[^"\s]+)\s+(.+)', phrase)
    if match:
        return _field(frame, match[2]), match[1]
    raise AnalysisQuestion('Name the filter column and value, for example "Outcome" = "Yes".')


def _summary(frame: pd.DataFrame, question: str) -> AnalysisPlan | None:
    match = SUMMARY.fullmatch(question)
    if not match:
        return None
    operation = match[1].casefold()
    operation = AGGREGATIONS.get(operation, operation)
    detail = match[2]
    grouped = _split_phrase(detail, 'by|per')
    if grouped:
        return AnalysisPlan(operation, _field(frame, grouped[0]), group_by=_field(frame, grouped[1]))
    filtered = _split_phrase(detail, 'for|where')
    if filtered:
        column, value = _filter(frame, filtered[1])
        return AnalysisPlan(operation, _field(frame, filtered[0]), filter_column=column, filter_value=value)
    return AnalysisPlan(operation, _field(frame, detail))


def _plan(frame: pd.DataFrame, question: str) -> AnalysisPlan | None:
    match = MOST_MISSING.fullmatch(question)
    if match:
        group, measure = match.groups()
        return AnalysisPlan('grouped_missingness', _field(frame, measure), group_by=_field(frame, group))
    match = COMPARE_MISSING.fullmatch(question)
    grouped = _split_phrase(match[1], 'grouped by|by|per') if match else None
    if grouped:
        measure, group = grouped
        return AnalysisPlan('grouped_missingness', _field(frame, measure), group_by=_field(frame, group))
    match = MISSING_CAUSE.fullmatch(question)
    if match:
        return AnalysisPlan('missingness', _field(frame, match[1] or match[2]))
    match = LABEL_RATE.fullmatch(question)
    if match:
        return AnalysisPlan('rate', _field(frame, match[1]), filter_value=match[2], denominator='labelled')
    match = RATE[0].fullmatch(question)
    if match:
        return AnalysisPlan('rate', _field(frame, match[2]), filter_value=match[3], denominator='labelled')
    match = RATE[1].fullmatch(question)
    if match:
        column, label = _filter(frame, match[1])
        return AnalysisPlan('rate', column, filter_value=label, denominator='all_rows')
    if AMBIGUOUS_RATE.fullmatch(question):
        raise AnalysisQuestion('Should I use all rows or only labelled rows as the denominator? Include your choice in the question.')
    match = COUNT.fullmatch(question)
    if match:
        column, value = _filter(frame, match[1])
        return AnalysisPlan('count', filter_column=column, filter_value=value)
    return _summary(frame, question)


def _number(values: pd.Series, operation: str) -> float | None:
    if values.empty:
        return None
    result = float(values.agg(operation))
    if not math.isfinite(result):
        raise AnalysisQuestion('The result exceeds the supported numeric range.')
    return result


def _group_stats(frame: pd.DataFrame, plan: AnalysisPlan) -> tuple[str, dict]:
    group = frame[plan.group_by]
    if group.nunique(dropna=True) > explore_filters.MAX_CATEGORIES:
        raise AnalysisQuestion(f'Choose a grouping column with at most {explore_filters.MAX_CATEGORIES} observed values.')
    measure = frame[plan.measure]
    missing = plan.operation == 'grouped_missingness'
    named = group.notna()
    labels = analytics.category_labels(group.loc[named])
    observed = measure.loc[named].groupby(labels, sort=False, observed=True)

    def stats(label: str | None, rows: pd.Series) -> dict:
        if missing:
            count = int(rows.isna().sum())
            return {'group': label, 'matching_rows': len(rows), 'missing_rows': count,
                    'percent': round(100 * count / len(rows), 4) if len(rows) else None}
        usable = analytics.finite_numeric(rows)
        return {'group': label, 'matching_rows': len(rows), 'usable_rows': len(usable),
                'excluded_rows': len(rows) - len(usable),
                'value': _number(usable, plan.operation)}

    groups = [stats(str(label), rows) for label, rows in observed]
    if missing:
        groups.sort(key=lambda item: (-item['missing_rows'], item['group'].casefold()))
    else:
        groups.sort(key=lambda item: item['group'].casefold())
    blank = stats(None, measure.loc[~named])
    title = f'Missing {plan.measure} by {plan.group_by}' if missing else f'{plan.operation.title()} {plan.measure} by {plan.group_by}'
    return f'{title}.', {'groups': groups, 'blank_group': blank}


def _execute(frame: pd.DataFrame, plan: AnalysisPlan) -> tuple[str, dict, AnalysisPlan]:
    measure = frame[plan.measure] if plan.measure is not None else None
    if plan.operation == 'missingness':
        count = int(measure.isna().sum())
        return (f'{plan.measure} has {count:,} missing rows. The cause is unknown from the dataset alone. '
                'Check the source records or ask the data owner how these values were collected.',
                {'missing_rows': count, 'cause': None}, plan)
    if plan.operation == 'rate':
        label, matched = _label_mask(measure, plan.filter_value)
        labelled = int(measure.notna().sum())
        positives = int(matched.sum())
        unlabelled = len(frame) - labelled
        denominator = labelled if plan.denominator == 'labelled' else len(frame)
        percent = round(100 * positives / denominator, 4)
        if plan.denominator == 'labelled':
            text = (f'{positives:,} of {denominator:,} labelled rows in {plan.measure} match {label} '
                    f'({percent:g}%). The denominator excludes {unlabelled:,} unlabelled rows.')
        else:
            text = (f'{positives:,} of all {denominator:,} rows in {plan.measure} match {label} '
                    f'({percent:g}%). The denominator includes {unlabelled:,} unlabelled rows.')
        return (text, {'positives': positives, 'denominator': denominator, 'percent': percent},
                replace(plan, filter_column=plan.measure, filter_value=label))

    if plan.operation not in ('count', 'grouped_missingness') and (
        not pd.api.types.is_numeric_dtype(measure) or pd.api.types.is_bool_dtype(measure)
    ):
        raise AnalysisQuestion(f'Choose a numeric measure. {plan.measure!r} is not a numeric column.')
    if plan.group_by is not None:
        text, facts = _group_stats(frame, plan)
        return text, facts, plan

    matching = len(frame)
    if plan.filter_column is not None:
        label, mask = _label_mask(frame[plan.filter_column], plan.filter_value)
        plan = replace(plan, filter_value=label)
        matching = int(mask.sum())
        if measure is not None:
            measure = measure.loc[mask]
    filter_text = f' where {plan.filter_column} = {plan.filter_value}' if plan.filter_column is not None else ''
    if plan.operation == 'count':
        return f'{matching:,} matching rows{filter_text}.', {'matching_rows': matching}, plan
    usable = analytics.finite_numeric(measure)
    result = _number(usable, plan.operation)
    text = f'{plan.operation.title()} {plan.measure}{filter_text}'
    value = f'is {result:,.12g}' if result is not None else 'is unavailable'
    return (f'{text} {value}. {len(usable):,} usable values from {matching:,} matching rows. '
            f'{matching - len(usable):,} missing or non-finite values excluded.',
            {'value': result, 'matching_rows': matching, 'usable_rows': len(usable),
             'excluded_rows': matching - len(usable)}, plan)


def _follow_up(frame: pd.DataFrame, project_id: str, version: int, previous: FollowUp | None, value: str) -> AnalysisPlan:
    if previous is not None and (previous.project_id, previous.dataset_version) == (project_id, version):
        plan = _summary(frame, _clean(previous.question))
        if plan and plan.filter_column is not None:
            _label_mask(frame[plan.filter_column], plan.filter_value)
            return replace(plan, filter_value=value)
    raise AnalysisQuestion('Which calculation should I use for this filter? Ask a new question about the current dataset.')


def _clean(question: str) -> str:
    return question.strip().rstrip('?.').strip()


def answer(frame: pd.DataFrame, version: int, project_id: str, question: str,
           previous: FollowUp | None = None) -> dict:
    question = _clean(question)
    folded = question.casefold()
    if OVERVIEW.fullmatch(folded):
        facts = analytics.dataset_counts(frame)
        text = (f"Working dataset v{version} has {facts['rows']:,} rows, {facts['columns']:,} columns, "
                f"{facts['missing_cells']:,} missing cells and {facts['exact_duplicate_rows']:,} exact duplicate rows.")
        return {'answer': text, 'facts': facts, 'analysis': {'operation': 'overview'}}
    if TRAINING.fullmatch(folded):
        text, facts = training_answer(project_id, version)
        return {'answer': text, 'facts': facts, 'analysis': {'operation': 'training_status'}}
    if MISSING_OVERVIEW.fullmatch(folded):
        missing = frame.isna().sum()
        found = missing[missing > 0].sort_values(ascending=False, kind='stable').head(12)
        text = ', '.join(f'{column}: {count:,}' for column, count in found.items()) or 'none detected'
        facts = {'missing_by_column': {name: int(count) for name, count in found.items()}}
        return {'answer': f'Missing values by column: {text}.', 'facts': facts,
                'analysis': {'operation': 'missingness_overview'}}
    follow = FOLLOW_UP.fullmatch(question)
    try:
        plan = _follow_up(frame, project_id, version, previous, follow[1]) if follow else _plan(frame, question)
        if plan is not None:
            text, facts, plan = _execute(frame, plan)
            if plan.group_by is not None:
                # The response carries structured per-group facts for the local UI.
                # The answer still names the columns for text-only clients.
                text += f" {facts['blank_group']['matching_rows']:,} rows have a blank {plan.group_by}."
            next_turn = None
            if not follow and SUMMARY.fullmatch(question) and plan.filter_column is not None:
                next_turn = asdict(FollowUp(project_id, version, question))
            return {'answer': text, 'facts': facts, 'analysis': asdict(plan), 'follow_up': next_turn}
    except AnalysisQuestion as exc:
        return {'answer': str(exc), 'facts': {}, 'analysis': None}

    return {'answer': 'Local analytics could not interpret this request. Try a dataset overview, missing values by group, '
            'an explicit percentage, a filtered numeric summary or training status.',
            'facts': {}, 'analysis': None}


def training_answer(project_id: str, version: int) -> tuple[str, dict]:
    experiment = storage.latest_version_training(project_id, version)
    if not experiment:
        return ('No training start is recorded for this dataset version. No validation score is available.',
                {'training_started': False, 'validation_score': None})
    results = experiment['results'] or {}
    model = next((m for m in results.get('models', [])
                  if m.get('key') == experiment['selected_model'] and m.get('status') == 'ready'), None)
    score = model.get('cv_metric') if model and experiment['status'] == 'completed' else None
    if type(score) not in (int, float) or not math.isfinite(score):
        score = None
    facts = {'training_started': True, 'validation_score': score}
    if score is None:
        return ('Training started for this dataset version. No cross-validation score is available for a selected model.', facts)
    return (f"Training started for this dataset version. The selected model's recorded cross-validation score "
            f"({results.get('primary_metric') or 'CV metric'}) is {score:g}.", facts)
