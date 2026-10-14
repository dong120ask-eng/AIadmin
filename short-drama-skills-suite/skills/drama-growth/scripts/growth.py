import argparse
import csv
import json
import math
from pathlib import Path
import sys

GROUP = ['platform', 'account', 'language', 'genre', 'cohort', 'window_hours', 'episode_seconds']
COUNTS = ['plays', 'starts', 'retained_starts', 'completions', 'next_episode_clicks', 'likes']
RATES = {'retention': ('retained_starts', 'starts'), 'completion': ('completions', 'starts'), 'continuation': ('next_episode_clicks', 'starts'), 'like_rate': ('likes', 'plays')}


def interval(successes, total):
    if not total:
        return None
    p, z = successes / total, 1.96
    denominator = 1 + z*z/total
    mid = (p + z*z/(2*total))/denominator
    width = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total))/denominator
    return [max(0, mid-width), min(1, mid+width)]


def analyze(rows, minimum=200):
    groups, seen = {}, set()
    for raw in rows:
        if any(not raw.get(k) for k in GROUP + ['content_id', 'variant']):
            raise ValueError('identity and comparison fields required')
        identity = tuple(raw[k] for k in GROUP + ['content_id', 'variant'])
        if identity in seen:
            raise ValueError('duplicate metric snapshot')
        seen.add(identity)
        row = dict(raw)
        for k in COUNTS:
            value = raw.get(k, '')
            if value != '' and (not str(value).isdigit()):
                raise ValueError('counts must be nonnegative integers; unknown metrics stay blank')
            row[k] = int(value) if value != '' else None
        for numerator, denominator in RATES.values():
            if row[numerator] is not None and row[denominator] is not None and row[numerator] > row[denominator]:
                raise ValueError('metric exceeds corresponding denominator')
        key = tuple(row[k] for k in GROUP + ['variant'])
        groups.setdefault(key, []).append(row)
    result = []
    for key, entries in groups.items():
        item = dict(zip(GROUP + ['variant'], key))
        item['content_ids'] = [x['content_id'] for x in entries]
        item['rates'] = {}
        for metric, (num, den) in RATES.items():
            valid = [x for x in entries if x[num] is not None and x[den] is not None]
            n = sum(x[num] for x in valid)
            d = sum(x[den] for x in valid)
            item['rates'][metric] = {'value': n/d if d else None, 'numerator': n if valid else None, 'denominator': d if valid else None, 'wilson_95': interval(n, d), 'sample_sufficient_for_descriptive_review': d >= minimum}
        item['comparison_status'] = 'descriptive_only_not_causal_ab_result'
        result.append(item)
    return {'minimum_sample_for_review': minimum, 'groups': result, 'causal_claims_supported': False, 'cross_platform_ranking': False}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser()
    p.add_argument('--csv', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--minimum-sample', type=int, default=200)
    a = p.parse_args()
    if a.minimum_sample < 1:
        p.error('minimum sample must be positive')
    with Path(a.csv).open(encoding='utf-8-sig', newline='') as f:
        report = analyze(list(csv.DictReader(f)), a.minimum_sample)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'metrics-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    feedback = ['# 下一轮导演复盘', '', '指标只作描述，先核对后台口径与人群/曝光条件，不直接认定因果或爆款。', '']
    for group in report['groups']:
        feedback.append(f"- {group['platform']} / {group['variant']} / {group['genre']}：" + '；'.join(k + '=' + (f"{v['value']:.1%}" if v['value'] is not None else '未测量') for k, v in group['rates'].items()))
    feedback += ['', '按同条件比较后选择一个变量：开场理解与情绪承诺、单集任务与兑现、集尾承接、声画质量或标题封面匹配。先做对照样片，再根据新数据决定是否扩大生产；不得用主观打分代替真实观看数据。']
    (out / 'director-feedback.md').write_text('\n'.join(feedback), encoding='utf-8')
    print(json.dumps({'groups': len(report['groups']), 'causal_claims_supported': False}))


if __name__ == '__main__':
    main()
