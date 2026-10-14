"""Genre selection, speech heuristics and review gates shared by the pipeline."""
import json
import math
from pathlib import Path
import re


def catalog():
    return json.loads((Path(__file__).parent.parent / 'assets/genre-frameworks.json').read_text(encoding='utf-8'))


def genre_spec(value):
    if isinstance(value, str):
        value = {'primary': value, 'secondary': [], 'tropes': []}
    if not isinstance(value, dict):
        raise ValueError('genre must be a code or object')
    primary = value.get('primary', 'general')
    secondary = value.get('secondary', [])
    tropes = value.get('tropes', [])
    if not isinstance(secondary, list) or len(secondary) > 2 or len(set(secondary)) != len(secondary) or primary in secondary:
        raise ValueError('choose one primary genre and up to two distinct secondary genres')
    if not isinstance(tropes, list) or any(not isinstance(x, str) for x in tropes):
        raise ValueError('tropes must be a string list')
    choices = catalog()['genres']
    if primary not in choices or any(x not in choices for x in secondary):
        raise ValueError('unknown genre code; use genres command to list supported codes')
    return {'primary': primary, 'secondary': secondary, 'tropes': tropes}


def rules_for(spec):
    spec = genre_spec(spec)
    data = catalog()
    return {'selection': spec, 'common': data['common'], 'primary': data['genres'][spec['primary']], 'secondary': [data['genres'][x] for x in spec['secondary']], 'evidence_level': data['evidence_level']}


def speech_seconds(text, language='zh-CN', han_per_second=3.5):
    # Planning heuristic only; ASR/audio duration remains the final measurement.
    han = len(re.findall(r'[\u3400-\u9fff]', text))
    words = len(re.findall(r'[A-Za-z0-9]+(?:[\x27’-][A-Za-z0-9]+)*', text))
    punctuation = len(re.findall(r'[，。！？、,.;:!?]', text))
    other = len(re.findall(r'[^\u3400-\u9fffA-Za-z0-9\s\W]', text))
    return han / han_per_second + words / 2.5 + other / 5 + punctuation * .12


def review_verdict(report, script, rules, minimum=16):
    dimensions = catalog()['common']['dimensions']
    scores = report.get('scores', {})
    if set(scores) != set(dimensions) or any(type(x) is not int or not 0 <= x <= 2 for x in scores.values()):
        raise ValueError('review requires all ten integer dimension scores in 0..2')
    ids = {x['id'] for x in script['shots']}
    evidence = report.get('dimension_evidence', {})
    if set(evidence) != set(dimensions):
        raise ValueError('review requires evidence for every dimension')
    for value in evidence.values():
        if not isinstance(value, dict) or not value.get('reason') or not value.get('shot_ids') or not set(value['shot_ids']) <= ids:
            raise ValueError('review evidence must reference actual shot IDs')
    checks = report.get('genre_checks', [])
    expected = set(rules['primary']['review_checks'])
    if not isinstance(checks, list) or len(checks) != len(expected) or {x.get('criterion') for x in checks} != expected:
        raise ValueError('review must assess every primary genre criterion exactly once')
    for item in checks:
        if type(item.get('pass')) is not bool or not item.get('reason') or not item.get('shot_ids') or not set(item['shot_ids']) <= ids:
            raise ValueError('genre check requires boolean and real evidence')
    issues = report.get('issues')
    if not isinstance(issues, list):
        raise ValueError('review issues must be a list')
    for item in issues:
        if item.get('severity') not in ['blocker', 'major', 'minor'] or not item.get('reason') or not item.get('repair'):
            raise ValueError('review issues require severity, reason and repair')
        if not item.get('shot_ids') or not set(item['shot_ids']) <= ids:
            raise ValueError('review issues must reference actual shots')
    passed = min(scores.values()) >= 1 and sum(scores.values()) >= minimum and all(x['pass'] for x in checks) and not any(x['severity'] in ['blocker', 'major'] for x in issues)
    return {'passed': passed, 'total': sum(scores.values()), 'maximum': 20, 'assessment': 'model_editorial_review_not_virality_prediction'}
