from __future__ import annotations

import json

from dynamic_consent_hri.research.analyze_trials import analyze, aggregate_trials
from dynamic_consent_hri.research.decision_policies import synthetic_decision


def _trial(condition='dynamic', strategy='alternate'):
    return {
        'schema_version': 1,
        'synthetic_trial': True,
        'condition': condition,
        'decision_strategy': strategy,
        'duration_seconds': 10.0,
        'metrics': {
            'completion_rate': 1.0,
            'stage_count': 7,
            'granted_stage_count': 4,
            'fallback_stage_count': 3,
            'odometry_delta_x': 1.6,
        },
    }


def test_synthetic_strategies_are_deterministic():
    assert synthetic_decision('grant_all', 'speech_input', 2)
    assert not synthetic_decision('refuse_all', 'speech_input', 2)
    assert synthetic_decision('alternate', 'person_recognition', 1)
    assert not synthetic_decision('alternate', 'speech_input', 2)
    assert not synthetic_decision(
        'risk_weighted', 'remote_assistance_stream', 7)


def test_aggregate_groups_condition_and_strategy():
    rows = aggregate_trials([_trial(), _trial('static', 'grant_all')])
    assert len(rows) == 2
    assert rows[0]['trial_count'] == 1


def test_analyze_writes_summary_and_linddun_report(tmp_path):
    source = tmp_path / 'input'
    output = tmp_path / 'output'
    source.mkdir()
    (source / 'trial.json').write_text(
        json.dumps(_trial()), encoding='utf-8')

    count, groups = analyze(source, output)

    assert (count, groups) == (1, 1)
    assert (output / 'research_summary.csv').is_file()
    assert (output / 'linddun_assessment.json').is_file()
    assert 'Unawareness' in (output / 'linddun_assessment.md').read_text(
        encoding='utf-8')
