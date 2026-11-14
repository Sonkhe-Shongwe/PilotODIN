"""Synthetic answer checks and verified model inputs for the Windows worker comparison."""
from __future__ import annotations

import json
from pathlib import Path

from verify_inference_assets import sha256


CANDIDATES = {
    'qwen3-0.6b-q4-k-m': (
        'https://huggingface.co/bartowski/Qwen_Qwen3-0.6B-GGUF/resolve/60b85c0e3d8fe0f6474f406922a26d12aca4550d/Qwen_Qwen3-0.6B-Q4_K_M.gguf',
        484220320,
        '9acfc1e001311f34b4252001b626f2e466d592a42065f66571bff3790d4e1b14',
    ),
    'smollm2-360m-q4-k-m': (
        'https://huggingface.co/lmstudio-community/SmolLM2-360M-Instruct-GGUF/resolve/b4c62446992d1feec0ef87d60af9b12ac8922919/SmolLM2-360M-Instruct-Q4_K_M.gguf',
        270590592,
        'e55c2a5df7f8f6eed1a843ff709fa8008dbce65d82e57c5c06dec5ee8d060415',
    ),
}

SYSTEM = (
    'You are ODIN, an evidence-grounded data science adviser. '
    'Use only the verified facts. Never invent statistics, causal relationships or findings. '
    'Answer with one JSON object using exactly the requested keys. Use JSON null for an unknown value.'
)

CASES = (
    (
        'dataset_overview',
        {'rows': 80, 'columns': 5, 'missing_cells': 0, 'exact_duplicate_rows': 0},
        'Report the dataset dimensions and quality counts using keys rows, columns, missing_cells, exact_duplicate_rows.',
        {'rows': 80, 'columns': 5, 'missing_cells': 0, 'exact_duplicate_rows': 0},
    ),
    (
        'rate_with_denominator',
        {'positive_labels': 12, 'labelled_rows': 60, 'all_rows': 80, 'positive_pct_of_labelled': 20},
        'Report the number of positives, the denominator for the labelled rate, and that rate as a numeric percent. Use keys positives, denominator, percent.',
        {'positives': 12, 'denominator': 60, 'percent': 20},
    ),
    (
        'unknown_cause',
        {'missing_premium_rows': 7, 'source_system_log_available': False},
        'Report the number of missing premium rows and the cause of the missingness. Use keys missing_rows and cause.',
        {'missing_rows': 7, 'cause': None},
    ),
    (
        'no_training_claim',
        {'target_reviewed': True, 'training_started': False, 'validation_score': None},
        'Report whether training started and the validation score. Use keys training_started and validation_score.',
        {'training_started': False, 'validation_score': None},
    ),
)


def verified_candidate(name: str, file: Path) -> Path:
    _, size, expected_hash = CANDIDATES[name]
    with file.open('rb') as model:
        if file.stat().st_size != size or model.read(4) != b'GGUF':
            raise ValueError(f'{name}: unexpected size or GGUF signature')
    if sha256(file) != expected_hash:
        raise ValueError(f'{name}: model checksum mismatch')
    return file.resolve()


def score_answer(content: str, expected: dict) -> bool:
    text = content.strip()
    if text.startswith('```json\n') and text.endswith('\n```'):
        text = text[len('```json\n'):-len('\n```')]
    def unique_object(pairs):
        result = dict(pairs)
        if len(result) != len(pairs):
            raise ValueError('Duplicate answer keys')
        return result

    try:
        answer = json.loads(text, object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        return False
    return (
        isinstance(answer, dict)
        and answer.keys() == expected.keys()
        and all(answer[key] == value and (
            type(answer[key]) in (int, float) if type(value) is int else type(answer[key]) is type(value)
        ) for key, value in expected.items())
    )
