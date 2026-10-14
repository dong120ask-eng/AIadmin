import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from datetime import date
import math


def build(data):
    for key in ['platform', 'audience', 'genre', 'research_window']:
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError('missing research context: ' + key)
    cases = data.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('at least one documented case required')
    for case in cases:
        parsed = urlparse(case.get('url', ''))
        if parsed.scheme != 'https' or not parsed.hostname or not case.get('title') or not case.get('observation'):
            raise ValueError('case requires title, observation and HTTPS source')
        date.fromisoformat(case['accessed_at'])
        level = case.get('evidence_level')
        if level not in ['A', 'B', 'C'] or case.get('material') not in ['synopsis', 'clip', 'transcript', 'full_episodes']:
            raise ValueError('invalid evidence level/material')
        if level in ['A', 'B'] and (case['material'] == 'synopsis' or not case.get('episode') or not case.get('timecode')):
            raise ValueError('strong evidence requires episode and timecode in observed material')
        known = 0
        for metric in case.get('metrics', []):
            for field in ['name', 'unit', 'window', 'source']:
                if not metric.get(field):
                    raise ValueError('metric requires name/unit/window/source')
            value = metric.get('value')
            if value is None:
                if not metric.get('missing_reason'):
                    raise ValueError('unknown metric requires missing_reason')
            elif type(value) not in [int, float] or not math.isfinite(value) or value < 0:
                raise ValueError('metric must be finite and nonnegative or null')
            else:
                known += 1
        if level == 'A' and not known:
            raise ValueError('A evidence requires at least one verifiable metric')
    hypotheses = data.get('hypotheses', [])
    if not hypotheses or any(not all(x.get(k) for k in ['change', 'expected_metric', 'reason', 'disconfirming_signal']) for x in hypotheses):
        raise ValueError('hypothesis requires observable change, metric and disconfirming signal')
    limitations = list(data.get('limitations', []))
    if not any(x.get('counterexample') for x in cases):
        limitations.append('未取得反例，存在幸存者偏差')
    if all(x['evidence_level'] == 'C' for x in cases):
        limitations.append('只有简介与假设，不能推断实际节奏或点赞成因')
    return {**data, 'schema_version': 1, 'limitations': list(dict.fromkeys(limitations)), 'causal_claims_supported': False, 'automatically_verified': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--out', required=True)
    a = p.parse_args()
    result = build(json.loads(Path(a.input).read_text(encoding='utf-8-sig')))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'cases': len(result['cases']), 'automatically_verified': False}))


if __name__ == '__main__':
    main()
