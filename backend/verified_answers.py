"""Read-only answers to supported Ask ODIN questions on a working version."""

from __future__ import annotations

import math
import re

import pandas as pd

try:
    from . import analytics, storage
except ImportError:
    import analytics, storage


OVERVIEW = re.compile(r'(?:what is the dataset overview|dataset overview|give me (?:a|the) dataset overview|report the dataset dimensions and quality counts)')
MISSING_CAUSE = re.compile(r'(?:why (?:are values missing|is data missing) (?:in|from)|missing count and cause for) "([^"\r\n]+)"', re.I)
LABEL_RATE = re.compile(r'(?:what is the )?(?:labelled |labeled )?positive rate for "([^"\r\n]+)"\s*=\s*"([^"\r\n]+)"', re.I)
TRAINING = re.compile(r'(?:training status|has training started(?: for this dataset)?|report whether training started and the validation score)')


def answer(frame: pd.DataFrame, version: int, project_id: str, question: str) -> tuple[str, dict] | None:
    question = question.strip().rstrip('?.').strip()
    if OVERVIEW.fullmatch(question.casefold()):
        facts = analytics.dataset_counts(frame)
        return (f"Working dataset v{version} has {facts['rows']:,} rows, {facts['columns']:,} columns, "
                f"{facts['missing_cells']:,} missing cells and {facts['exact_duplicate_rows']:,} exact duplicate rows.", facts)

    match = MISSING_CAUSE.fullmatch(question)
    if match:
        column = match[1]
        if column not in frame:
            return 'Use an existing column name in double quotes.', {}
        count = int(frame[column].isna().sum())
        return (f'{column} has {count:,} missing rows. The cause is unknown from the dataset alone. '
                'Check the source records or ask the data owner how these values were collected.',
                {'missing_rows': count, 'cause': None})

    match = LABEL_RATE.fullmatch(question)
    if match:
        column, positive_label = match.groups()
        if column not in frame:
            return 'Use an existing outcome column in double quotes.', {}
        labelled = frame[column].dropna()
        positives = int(labelled.astype(str).eq(positive_label).sum())
        if not positives:
            return 'Use an observed positive label, with the exact spelling shown in the dataset.', {}
        percent = round(100 * positives / len(labelled), 4)
        return (f'{positives:,} of {len(labelled):,} labelled rows in {column} match {positive_label} '
                f'({percent:g}%). The denominator excludes {len(frame) - len(labelled):,} unlabelled rows.',
                {'positives': positives, 'denominator': len(labelled), 'percent': percent})

    if TRAINING.fullmatch(question.casefold()):
        return training_answer(project_id, version)
    return None


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
