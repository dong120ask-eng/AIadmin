import hashlib
import math
from pathlib import Path
from urllib.parse import urlparse


def reject_credentials(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in {'api_key', 'apikey', 'ark_api_key', 'authorization', 'access_token', 'secret_key'}:
                raise ValueError('credentials must use stdin/environment, not project or asset JSON')
            reject_credentials(child)
    elif isinstance(value, list):
        for child in value:
            reject_credentials(child)


def file_sha256(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            sha.update(chunk)
    return sha.hexdigest()


def media_signature(folder, script, render):
    records = []
    for shot in script['shots']:
        for suffix in ['.mp4', '.wav']:
            path = Path(folder) / 'shots' / f"{shot['id']:03d}{suffix}"
            stat = path.stat() if path.exists() else None
            records.append({'name': path.name, 'size': stat.st_size if stat else None, 'mtime_ns': stat.st_mtime_ns if stat else None})
    return {'files': records, 'render': render}


def reference_content(manifest, key, config):
    items = manifest.get('shots', {}).get(key, [])
    if not items:
        return []
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        raise ValueError('references must be a list of objects')
    roles = [x.get('role') for x in items]
    image_roles = [x for x in roles if x in ['reference_image', 'first_frame', 'last_frame']]
    if any(x not in ['reference_image', 'first_frame', 'last_frame', 'reference_video', 'reference_audio'] for x in roles):
        raise ValueError('unsupported reference role')
    if any(x in ['first_frame', 'last_frame'] for x in roles) and not (roles == ['first_frame'] or roles == ['first_frame', 'last_frame']):
        raise ValueError('do not mix reference-image and first/last-frame modes')
    if image_roles and not config.get('reference_images_supported'):
        raise ValueError('reference images require verified model support')
    if len(image_roles) > config.get('max_reference_images', 3):
        raise ValueError('reference image count exceeds configured model limit')
    if any(x in ['reference_video', 'reference_audio'] for x in roles) and not config.get('multimodal_references_supported'):
        raise ValueError('multimodal references require verified model support')
    if roles and all(x == 'reference_audio' for x in roles) and not config.get('audio_only_reference_supported'):
        raise ValueError('audio-only reference requires verified model support')
    for role in ['reference_video', 'reference_audio']:
        subset = [x for x in items if x.get('role') == role]
        kind = role.removeprefix('reference_')
        if len(subset) > config.get('max_reference_' + kind + 's', 3):
            raise ValueError('reference count exceeds configured model limit')
        durations = [x.get('duration_seconds') for x in subset]
        maximum = config.get('max_reference_' + kind + '_seconds', 15)
        if any(type(d) not in [int, float] or not math.isfinite(d) or not 2 <= d <= maximum for d in durations) or sum(durations) > maximum:
            raise ValueError('reference duration missing or exceeds verified model limit')
    content = []
    for item in items:
        if not item.get('rights_confirmed') or item.get('contains_real_face') or item['role'] == 'reference_audio' and not item.get('voice_consent_confirmed'):
            raise ValueError('reference must have cleared rights and comply with model face restrictions')
        url = item.get('url', '')
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('reference images need provider-accessible HTTPS URLs')
        kind = {'reference_video': 'video_url', 'reference_audio': 'audio_url'}.get(item['role'], 'image_url')
        content.append({'type': kind, kind: {'url': url}, 'role': item['role']})
    return content
