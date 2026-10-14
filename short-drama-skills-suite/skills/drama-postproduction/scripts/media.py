import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap


def probe(path):
    return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], encoding='utf-8'))


def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'


def write_srt(cues, duration, output):
    segments = cues.get('segments', [])
    if not segments:
        raise ValueError('timed subtitle segments required')
    previous, chunks = 0.0, []
    for i, cue in enumerate(segments, 1):
        start, end = cue['start'], cue['end']
        if any(type(x) not in [int, float] or not math.isfinite(x) for x in [start, end]) or not previous <= start < end <= duration + .05 or not str(cue['text']).strip():
            raise ValueError('subtitle times must be ordered, nonoverlapping and within video')
        chunks.append(f"{i}\n{stamp(start)} --> {stamp(end)}\n{cue['text']}\n")
        previous = end
    Path(output).write_text('\n'.join(chunks), encoding='utf-8')
    return {'segments': len(segments), 'timing_validation': True, 'listen_review_required': True}


def run(cmd, cwd=None):
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *cmd], cwd=cwd, check=True)


def burn(video, srt, output):
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(srt, Path(tmp) / 'captions.srt')
        run(['-i', str(Path(video).resolve()), '-vf', "subtitles=filename=captions.srt:force_style='FontName=Microsoft YaHei,FontSize=18,Outline=1,MarginV=32'", '-c:v', 'libx264', '-c:a', 'copy', str(Path(output).resolve())], cwd=tmp)


def cover(video, seconds, title, font, output):
    duration = float(probe(video)['format']['duration'])
    if not math.isfinite(seconds) or not 0 <= seconds < duration:
        raise ValueError('cover time outside video')
    with tempfile.TemporaryDirectory() as tmp:
        filters = 'scale=1080:1440:force_original_aspect_ratio=increase,crop=1080:1440'
        if title:
            if not font:
                raise ValueError('provide a readable Chinese font file for title')
            shutil.copyfile(font, Path(tmp) / 'font.ttf')
            (Path(tmp) / 'title.txt').write_text('\n'.join(textwrap.wrap(title, 14)), encoding='utf-8')
            filters += ',drawtext=fontfile=font.ttf:textfile=title.txt:fontsize=64:fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*0.75'
        run(['-ss', str(seconds), '-i', str(Path(video).resolve()), '-frames:v', '1', '-vf', filters, str(Path(output).resolve())], cwd=tmp)


def mix(video, music, gain, output):
    if not 0 <= gain <= 1:
        raise ValueError('music gain must be 0..1')
    data = probe(video)
    if not any(x['codec_type'] == 'audio' for x in data['streams']):
        raise ValueError('video needs a dialogue/environment audio track')
    run(['-i', str(video), '-stream_loop', '-1', '-i', str(music), '-filter_complex', f'[1:a]volume={gain}[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]', '-map', '0:v:0', '-map', '[a]', '-t', data['format']['duration'], '-c:v', 'copy', '-c:a', 'aac', '-ar', '48000', str(output)])


def qc(video):
    data = probe(video)
    cmd = ['ffmpeg', '-hide_banner', '-i', str(video), '-vf', 'blackdetect=d=0.5:pix_th=0.1', '-af', 'silencedetect=n=-40dB:d=2', '-f', 'null', '-']
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace')
    events = [line.strip() for line in result.stderr.splitlines() if re.search(r'black_start:|silence_start:|silence_end:', line)]
    h = hashlib.sha256()
    with Path(video).open('rb') as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return {'video': str(Path(video).resolve()), 'sha256': h.hexdigest(), 'duration': float(data['format']['duration']), 'streams': [{'type': s['codec_type'], 'codec': s.get('codec_name'), 'width': s.get('width'), 'height': s.get('height')} for s in data['streams']], 'scan_completed': result.returncode == 0, 'candidate_events': events, 'human_review_required': True, 'blackframe_or_silence_is_not_automatic_failure': True}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['subtitles', 'burn', 'cover', 'mix', 'qc'])
    p.add_argument('--video', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--cues')
    p.add_argument('--srt')
    p.add_argument('--music')
    p.add_argument('--gain', type=float, default=.12)
    p.add_argument('--time', type=float, default=0)
    p.add_argument('--title', default='')
    p.add_argument('--font')
    a = p.parse_args()
    if Path(a.video).resolve() == Path(a.out).resolve():
        raise ValueError('output must differ from source')
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    if a.command == 'subtitles':
        if not a.cues:
            p.error('subtitles requires --cues')
        result = write_srt(json.loads(Path(a.cues).read_text(encoding='utf-8-sig')), float(probe(a.video)['format']['duration']), a.out)
    elif a.command == 'burn':
        if not a.srt:
            p.error('burn requires --srt')
        burn(a.video, a.srt, a.out)
        result = {'status': 'burned_needs_preview'}
    elif a.command == 'cover':
        cover(a.video, a.time, a.title, a.font, a.out)
        result = {'status': 'cover_needs_preview'}
    elif a.command == 'mix':
        if not a.music:
            p.error('mix requires --music')
        mix(a.video, a.music, a.gain, a.out)
        result = {'status': 'mixed_needs_listening'}
    else:
        result = qc(a.video)
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
