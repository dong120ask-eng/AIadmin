import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

DOMESTIC = {'hongguo', 'douyin', 'kuaishou', 'bilibili', 'xiaohongshu', 'wechat-channels'}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk := f.read(1024*1024):
            h.update(chunk)
    return h.hexdigest()


def prepare(manifest, platform, account):
    result = []
    for row in manifest:
        if row['platform'] != platform:
            continue
        video = Path(row['video'])
        missing = []
        asset_hash = sha(video) if video.is_file() else None
        if not asset_hash:
            missing.append('video_missing')
        if row.get('asset_sha256') and row['asset_sha256'] != asset_hash:
            missing.append('video_changed_after_manifest')
        if not Path(row['subtitle']).is_file():
            missing.append('subtitle_missing')
        qc = row.get('qc') or {}
        if not (row.get('script_review') or {}).get('passed'):
            missing.append('script_review_not_passed')
        if not row.get('asset_sha256'):
            missing.append('manifest_video_hash_missing')
        subtitle_hash = sha(row['subtitle']) if Path(row['subtitle']).is_file() else None
        approval = row.get('human_review') or {}
        if approval.get('asset_sha256') != asset_hash or approval.get('subtitle_sha256') != subtitle_hash or not approval.get('reviewer') or not approval.get('reviewed_at'):
            missing.append('human_review_missing_or_stale')
        for flag in ['mechanical_pass', 'voice_reviewed', 'visual_reviewed', 'subtitle_aligned']:
            if not qc.get(flag):
                missing.append(flag)
        if row.get('media_current') is not True:
            missing.append('media_changed_since_qc')
        for flag in ['original_or_licensed', 'music_cleared', 'voice_cleared']:
            if not row.get('rights', {}).get(flag):
                missing.append(flag)
        if platform in DOMESTIC and (row.get('filing', {}).get('status') != 'approved' or not row.get('filing', {}).get('number')):
            missing.append('filing_or_platform_program_number')
        identity = {'platform': platform, 'account': account, 'episode': row['episode'], 'language': row['language'], 'asset_sha256': asset_hash}
        rid = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        result.append({**row, **identity, 'release_id': rid, 'ready': not missing, 'missing': missing, 'status': 'prepared' if not missing else 'blocked_materials', 'uploaded': False})
    if not result:
        raise ValueError('selected platform has no manifest entries')
    return result


def attest(manifest, reviewer):
    """Record the operator's completed review, bound to the final media and subtitle."""
    if not reviewer.strip():
        raise ValueError('reviewer required')
    for row in manifest:
        if not Path(row['video']).is_file() or not Path(row['subtitle']).is_file():
            raise ValueError('review requires existing final video and subtitle')
        if not (row.get('script_review') or {}).get('passed') or row.get('media_current') is not True:
            raise ValueError('review requires passed script and current media')
        actual = sha(row['video'])
        if actual != row.get('asset_sha256'):
            raise ValueError('final video changed: refresh manifest before review')
        row['human_review'] = {'asset_sha256': actual, 'subtitle_sha256': sha(row['subtitle']), 'reviewer': reviewer, 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'origin': 'operator_attestation_not_automated_perceptual_review'}
        row.setdefault('qc', {}).update(voice_reviewed=True, visual_reviewed=True, subtitle_aligned=True)
    return manifest


def record(queue, receipt, log):
    matches = [x for x in queue if x['release_id'] == receipt.get('release_id')]
    if len(matches) != 1:
        raise ValueError('receipt must identify one release entry')
    status = receipt.get('status')
    if status not in ['uploaded', 'submitted', 'in_review', 'published', 'rejected', 'unknown']:
        raise ValueError('invalid receipt status')
    if not receipt.get('evidence'):
        raise ValueError('backend evidence required')
    if status == 'published' and not (receipt.get('remote_id') or urlparse(receipt.get('url', '')).scheme == 'https'):
        raise ValueError('published requires real remote ID or HTTPS URL')
    existing = [json.loads(x) for x in Path(log).read_text(encoding='utf-8').splitlines() if x] if Path(log).exists() else []
    if any(x['release_id'] == receipt['release_id'] and x['status'] == 'published' for x in existing):
        return {'status': 'already_recorded_published', 'appended': False}
    entry = {**{k: matches[0][k] for k in ['platform', 'account', 'episode', 'language', 'asset_sha256', 'release_id']}, **{k: receipt.get(k) for k in ['status', 'remote_id', 'url', 'evidence']}, 'recorded_at': datetime.now(timezone.utc).isoformat(), 'origin': 'backend_observed_receipt_not_automatic_upload'}
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open('a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return {'status': status, 'appended': True}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['prepare', 'record', 'attest'])
    p.add_argument('--reviewer')
    p.add_argument('--review-completed', action='store_true')
    p.add_argument('--manifest')
    p.add_argument('--platform')
    p.add_argument('--account')
    p.add_argument('--queue')
    p.add_argument('--receipt')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    if a.command == 'prepare':
        if not all([a.manifest, a.platform, a.account]):
            p.error('prepare requires manifest, platform and account')
        rows = prepare(json.loads(Path(a.manifest).read_text(encoding='utf-8-sig')), a.platform, a.account)
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'queue.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        result = {'entries': len(rows), 'ready': sum(x['ready'] for x in rows), 'uploaded': False}
    elif a.command == 'attest':
        if not a.manifest or not a.reviewer or not a.review_completed:
            p.error('attest requires manifest, reviewer and explicit review-completed')
        rows = attest(json.loads(Path(a.manifest).read_text(encoding='utf-8-sig')), a.reviewer)
        Path(a.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        result = {'operator_attestation_recorded': True, 'entries': len(rows), 'uploaded': False}
    else:
        if not a.queue or not a.receipt:
            p.error('record requires queue and receipt')
        result = record(json.loads(Path(a.queue).read_text(encoding='utf-8-sig')), json.loads(Path(a.receipt).read_text(encoding='utf-8-sig')), a.out)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
