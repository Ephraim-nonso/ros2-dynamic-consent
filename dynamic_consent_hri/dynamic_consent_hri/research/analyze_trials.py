"""Aggregate synthetic trial summaries and emit a LINDDUN assessment."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable


LINDDUN_ASSESSMENT = (
    {
        'category': 'Linkability',
        'assets': 'session events, ROS topics, per-session files',
        'evidence': 'random session identifiers and one CSV per session',
        'controls': 'anonymous session rotation; closed event schema',
        'residual_risk': 'medium',
        'simulation_test': 'compare cross-trial identifiers and event ordering',
    },
    {
        'category': 'Identifiability',
        'assets': 'camera frames, audio, recognition data',
        'evidence': 'raw sensor data is excluded from ConsentEvent and CSV',
        'controls': 'local processing; derived boolean presence; no raw logging',
        'residual_risk': 'high',
        'simulation_test': 'verify no raw sensor fields occur in trial artifacts',
    },
    {
        'category': 'Non-repudiation',
        'assets': 'consent decisions and capability outcomes',
        'evidence': 'consent_decided, authorized, blocked, and execution events',
        'controls': 'durable anonymous audit log with closed event semantics',
        'residual_risk': 'low',
        'simulation_test': 'reconcile prompt decisions with stage outcomes',
    },
    {
        'category': 'Detectability',
        'assets': 'sensor activation and consent status topics',
        'evidence': 'authorized, blocked, and sensor status topics are observable',
        'controls': 'bounded windows and fail-closed guards',
        'residual_risk': 'medium',
        'simulation_test': 'check that denied stages produce no authorized outcome',
    },
    {
        'category': 'Disclosure of Information',
        'assets': 'raw audio, images, transcripts, model observations',
        'evidence': 'guards publish only bounded derived outputs to downstream nodes',
        'controls': 'memory-only audio path; no raw study logging; local recognition',
        'residual_risk': 'high',
        'simulation_test': 'inspect topic graph and artifact contents for raw payloads',
    },
    {
        'category': 'Unawareness',
        'assets': 'participant understanding of purpose and processing',
        'evidence': 'dynamic prompts expose purpose, inputs, recipients, retention',
        'controls': 'purpose-centred policy and static disclosure copy',
        'residual_risk': 'high_without_users',
        'simulation_test': 'verify prompt completeness; do not infer comprehension',
    },
    {
        'category': 'Non-compliance',
        'assets': 'policy-to-sensor enforcement and study protocol',
        'evidence': 'unknown, pending, revoked, expired, and missing-service paths deny',
        'controls': 'strict policy loader; privacy gate; fallbacks; logger fail-closed',
        'residual_risk': 'medium',
        'simulation_test': 'run refusal, revocation, reset, and service-failure trials',
    },
)


def _json_files(directory: Path) -> list[Path]:
    return sorted(directory.glob('*.json'))


def load_trials(paths: Iterable[Path]) -> list[dict]:
    trials = []
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or not data.get('synthetic_trial'):
            continue
        data['_source'] = path.name
        trials.append(data)
    return trials


def _metric(trial: dict, name: str, default=0):
    return trial.get('metrics', {}).get(name, default)


def aggregate_trials(trials: list[dict]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for trial in trials:
        grouped[(trial.get('condition', ''),
                 trial.get('decision_strategy', ''))].append(trial)

    rows = []
    for (condition, strategy), items in sorted(grouped.items()):
        durations = [item.get('duration_seconds') for item in items
                     if isinstance(item.get('duration_seconds'), (int, float))]
        progress = [_metric(item, 'odometry_delta_x') for item in items
                    if isinstance(_metric(item, 'odometry_delta_x'), (int, float))]
        rows.append({
            'condition': condition,
            'decision_strategy': strategy,
            'trial_count': len(items),
            'complete_trials': sum(
                _metric(item, 'completion_rate') == 1.0 for item in items),
            'mean_duration_seconds': round(mean(durations), 3)
            if durations else '',
            'mean_stage_count': round(mean(
                [_metric(item, 'stage_count') for item in items]), 3),
            'mean_granted_stage_count': round(mean(
                [_metric(item, 'granted_stage_count') for item in items]), 3),
            'mean_fallback_stage_count': round(mean(
                [_metric(item, 'fallback_stage_count') for item in items]), 3),
            'mean_odometry_delta_x': round(mean(progress), 3)
            if progress else '',
        })
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text('', encoding='utf-8')
        return
    with path.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_linddun_markdown(path: Path) -> None:
    lines = [
        '# LINDDUN assessment for the synthetic consent simulation',
        '',
        'This is a technical threat-model assessment, not evidence of user '
        'understanding or acceptance. `high_without_users` explicitly marks '
        'the Unawareness limitation.',
        '',
        '| Category | Assets | Evidence | Controls | Residual risk |',
        '|---|---|---|---|---|',
    ]
    for row in LINDDUN_ASSESSMENT:
        lines.append('| {category} | {assets} | {evidence} | {controls} | '
                     '{residual_risk} |'.format(**row))
    lines.extend(['', '## Simulation checks', ''])
    for row in LINDDUN_ASSESSMENT:
        lines.append(f"- **{row['category']}:** {row['simulation_test']}")
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def analyze(input_directory: Path, output_directory: Path) -> tuple[int, int]:
    trials = load_trials(_json_files(input_directory))
    output_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write_csv(output_directory / 'research_summary.csv',
               aggregate_trials(trials))
    (output_directory / 'linddun_assessment.json').write_text(
        json.dumps(list(LINDDUN_ASSESSMENT), indent=2) + '\n',
        encoding='utf-8')
    _write_linddun_markdown(output_directory / 'linddun_assessment.md')
    return len(trials), len(aggregate_trials(trials))


def main(args=None):
    parser = argparse.ArgumentParser(
        description='Aggregate dynamic_consent synthetic research trials')
    parser.add_argument('--input', required=True, type=Path,
                        help='directory containing research-driver JSON files')
    parser.add_argument('--output', type=Path,
                        help='directory for aggregate outputs; defaults to input')
    parsed = parser.parse_args(args)
    output = parsed.output or parsed.input
    trial_count, group_count = analyze(parsed.input, output)
    print(f'analysed {trial_count} trial(s) in {group_count} group(s)')
    print(f'wrote {output / "research_summary.csv"}')
    print(f'wrote {output / "linddun_assessment.md"}')


if __name__ == '__main__':
    main()
