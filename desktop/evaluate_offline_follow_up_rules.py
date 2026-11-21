"""Score a model-free follow-up selector against the fixed analytics summaries."""
from __future__ import annotations

import json
import re

from offline_analytics_cases import WORDING_SCENARIOS, wording_result


STOP_WORDS = frozenset(
    'a all am an and are as at be before by can check could do does for from how i if in is it '
    'my of on or our should so that the them these this to us use was we were what when where '
    'whether which will with would you your'.split()
)
MINIMUM_MATCHES = 2

# Original hosted questions remain in WORDING_SCENARIOS. These separate
# examples deliberately include wording with little literal overlap.
PARAPHRASES = {
    'dataset_overview': (
        'Should I validate the field types and acceptable ranges?',
        'How do I spot nearly identical entries that are spelled differently?',
    ),
    'rate_with_denominator': (
        'Should the percentage be divided by the count of labelled rows or the whole dataset?',
        'Could the cases with no labels make the rate unrepresentative of everyone?',
    ),
    'unknown_cause': (
        'Can I compare the blanks between groups to find a pattern?',
        'Who can tell me why those entries are blank?',
    ),
    'no_training_claim': (
        'Which checks belong in the plan before fitting the model?',
        'Is a finished validation result required before I publish the performance?',
    ),
}
UNCLEAR = {
    'dataset_overview': ('What next?', 'How do I export a PDF?', 'Should I check column types and ranges or near-duplicate records?'),
    'rate_with_denominator': ('Which rate?', 'When was the file created?', 'Should I use the denominator for the positive rate or compare unlabelled and labelled rows?'),
    'unknown_cause': ('Can you explain?', 'Can I change the chart colours?', 'Should I compare missingness across groups or check source-system logs?'),
    'no_training_claim': ('What is the status?', 'How do I import another file?', 'Should I review the target and validation plan or report model performance?'),
}


def terms(text: str) -> set[str]:
    tokens = set(re.findall(r'[a-z]+', text.casefold())) - STOP_WORDS
    return {token[:-1] if len(token) > 4 and token.endswith('s') else token for token in tokens}


def select_follow_up(question: str, follow_ups: tuple[str, str]) -> str | None:
    question_terms = terms(question)
    first, second = map(terms, follow_ups)
    first_matches = len(question_terms & (first - second))
    second_matches = len(question_terms & (second - first))
    if first_matches >= MINIMUM_MATCHES and second_matches == 0:
        return 'A'
    if second_matches >= MINIMUM_MATCHES and first_matches == 0:
        return 'B'
    return None


def evaluate() -> dict:
    results = {'original': [], 'paraphrase': [], 'unclear': []}
    for name, summary, follow_ups, original in WORDING_SCENARIOS:
        for group, questions, expected_choices in (
            ('original', original, ('A', 'B')),
            ('paraphrase', PARAPHRASES[name], ('A', 'B')),
            ('unclear', UNCLEAR[name], (None, None, None)),
        ):
            for question, expected in zip(questions, expected_choices, strict=True):
                selection = select_follow_up(question, follow_ups)
                answer, selected = wording_result(summary, follow_ups, selection, 'stop')
                results[group].append({
                    'case': name, 'question': question, 'expected': expected,
                    'selected': selected, 'answer': answer,
                })
    return {
        group: {
            'correct': sum(row['expected'] == row['selected'] for row in rows),
            'wrong_selections': sum(row['selected'] is not None and row['expected'] != row['selected'] for row in rows),
            'abstentions': sum(row['selected'] is None for row in rows),
            'total': len(rows), 'cases': rows,
        }
        for group, rows in results.items()
    }


if __name__ == '__main__':
    print(json.dumps(evaluate(), indent=2))
