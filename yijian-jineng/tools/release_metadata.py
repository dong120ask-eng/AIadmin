"""Derive release identity and verify the exact asset and checksum pair."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import zipfile


def identity(version):
    match = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})-r([1-9]\d*)', version)
    if not match:
        raise ValueError('Invalid manifest version')
    year, month, day, revision = match.groups()
    datetime.date(int(year), int(month), int(day))
    return {'tag': f'v{year}.{month}.{day}-r{revision}',
            'asset': f'yijian-jineng-{year}{month}{day}-r{revision}.zip'}


def verify(directory, metadata):
    directory = Path(directory)
    asset = directory / metadata['asset']
    if {p.name for p in directory.iterdir()} != {metadata['asset'], 'SHA256.txt'}:
        raise ValueError('Unexpected or missing release files')
    with zipfile.ZipFile(asset) as archive:
        if archive.testzip() is not None:
            raise ValueError('Corrupt ZIP')
    expected = hashlib.sha256(asset.read_bytes()).hexdigest() + '  ' + metadata['asset'] + '\n'
    if (directory / 'SHA256.txt').read_text(encoding='utf-8') != expected:
        raise ValueError('Checksum or asset name mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default='yijian-jineng/config/skill-manifest.json')
    parser.add_argument('--output')
    parser.add_argument('--verify')
    args = parser.parse_args()
    metadata = identity(json.loads(Path(args.manifest).read_text(encoding='utf-8'))['version'])
    if args.verify:
        verify(args.verify, metadata)
    if args.output:
        with open(args.output, 'a', encoding='utf-8') as output:
            for key, value in metadata.items():
                output.write(f'{key}={value}\n')
    print(json.dumps(metadata))


if __name__ == '__main__':
    main()
