"""Portable Ark short-drama pipeline. Python stdlib + FFmpeg, no platform SDK."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse
from story_rules import catalog, genre_spec, rules_for, speech_seconds, review_verdict
from runtime_support import reject_credentials, reference_content, media_signature, file_sha256

BASE_URL = 'https://ark.cn-beijing.volces.com/api/v3'


def read_session_key(stream):
    key = stream.readline(8193).strip()
    if not key or len(key) > 8192 or any(char.isspace() for char in key):
        raise ValueError('provide one non-empty API key line through stdin')
    return key


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate(c):
    reject_credentials(c)
    if not isinstance(c['episodes'], int) or isinstance(c['episodes'], bool) or c['episodes'] < 1:
        raise ValueError('episodes must be a positive integer')
    if not 0 < c['minutes_per_episode'] <= 30:
        raise ValueError('minutes_per_episode must be in (0, 30]')
    if not str(c['topic']).strip():
        raise ValueError('topic required')
    langs = c['languages']
    if not langs or len(langs) != len(set(langs)) or any(not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', x) for x in langs):
        raise ValueError('languages must be unique BCP47-like codes')
    duration = c['ark']['video_options']['duration']
    if not isinstance(duration, int) or not 1 <= duration <= 30:
        raise ValueError('duration must be integer seconds; confirm model supports it')
    if not c['ark']['video_options'].get('generate_audio'):
        raise ValueError('native production requires generate_audio=true; otherwise supply shot WAV files')
    if urlparse(c['ark'].get('base_url', BASE_URL)).scheme != 'https':
        raise ValueError('Ark endpoint must be HTTPS')
    q = c.get('quality', {})
    if type(q.get('enabled', True)) is not bool or type(q.get('max_revisions', 2)) is not int or not 0 <= q.get('max_revisions', 2) <= 5:
        raise ValueError('quality requires boolean enabled and max_revisions in 0..5')
    if type(q.get('minimum_score', 16)) is not int or not 10 <= q.get('minimum_score', 16) <= 20:
        raise ValueError('minimum_score must be integer in 10..20')
    if not 1 <= q.get('han_per_second', 3.5) <= 6:
        raise ValueError('han_per_second must be in 1..6')
    if type(q.get('max_structure_retries', 1)) is not int or not 0 <= q.get('max_structure_retries', 1) <= 3:
        raise ValueError('max_structure_retries must be in 0..3')
    inflight = c.get('execution', {}).get('max_inflight_video_tasks', 1)
    if type(inflight) is not int or not 1 <= inflight <= 8:
        raise ValueError('max_inflight_video_tasks must be in 1..8')
    for key in ['max_text_calls', 'max_video_seconds']:
        if type(c['budget'].get(key)) is not int or c['budget'][key] < 0:
            raise ValueError('budget ' + key + ' must be a nonnegative integer')
    for key in ['text_call_estimate_cny', 'video_second_estimate_cny']:
        value = c['budget'].get(key)
        if value is not None and (type(value) not in [int, float] or not math.isfinite(value) or value < 0):
            raise ValueError('unit cost must be finite nonnegative or null')


class Pipeline:
    def __init__(self, config, out, api_key=None):
        validate(config)
        self.c, self.out = config, Path(out)
        self.quality = config.get('quality', {})
        self.review_required = self.quality.get('enabled', True)
        self.api_key = api_key
        self.brief = read(config['brief_path']) if config.get('brief_path') else {}
        reject_credentials(self.brief)
        asset_path = config.get('assets', {}).get('manifest_path')
        self.assets = read(asset_path) if asset_path else {}
        reject_credentials(self.assets)
        if config.get('brief_path'):
            b = self.brief
            if b.get('schema_version') not in [1, 2] or any(b.get(k) != config[k] for k in ['topic', 'episodes', 'minutes_per_episode']) or b.get('language') != config['source_language']:
                raise ValueError('director brief/config protocol mismatch')
            beats = b.get('episode_beats', [])
            if [x.get('episode') for x in beats] != list(range(1, config['episodes'] + 1)) or any(not all(x.get(k) for k in ['goal', 'obstacle', 'change', 'hook']) for x in beats):
                raise ValueError('director brief requires every episode beat')
            if b['schema_version'] == 2:
                genre_spec(b.get('genre'))
                if any(not all(x.get(k) for k in ['strategy', 'choice', 'consequence', 'payoff']) for x in beats):
                    raise ValueError('v2 director brief requires strategy, choice, consequence and payoff')
        configured_genre = config.get('genre', 'general')
        if configured_genre != 'auto':
            genre_spec(configured_genre)
        if self.brief.get('genre'):
            genre_spec(self.brief['genre'])
            if configured_genre != 'auto' and genre_spec(configured_genre) != genre_spec(self.brief['genre']):
                raise ValueError('director/config genre mismatch')
        self.out.mkdir(parents=True, exist_ok=True)
        self.sp = self.out / 'state.json'
        run_digest = digest({'config': config, 'brief': self.brief, 'frameworks': catalog(), 'assets': self.assets})
        self.state = read(self.sp) if self.sp.exists() else {'config_sha256': run_digest, 'text_calls': 0, 'video_seconds': 0, 'tasks': {}}
        if self.state['config_sha256'] != run_digest:
            raise ValueError('configuration changed: use a new run directory')
        self.persist()

    def persist(self):
        save(self.sp, self.state)

    def credential(self):
        return self.api_key or os.environ.get('ARK_API_KEY')

    def genres(self):
        return {k: v['label'] for k, v in catalog()['genres'].items()}

    def genre_rules(self):
        path = self.out / 'genre.json'
        if path.exists():
            selected = genre_spec(read(path))
        elif self.brief.get('genre'):
            selected = genre_spec(self.brief['genre'])
        elif self.c.get('genre', 'general') != 'auto':
            selected = genre_spec(self.c.get('genre', 'general'))
        else:
            selected = genre_spec(self.text('按话题和用户要求选择一个主类型，最多两个辅助类型；不要默认男频逆袭。返回JSON primary(类型代码),secondary(代码数组),tropes(桥段标签数组)。可选类型：' + json.dumps(self.genres(), ensure_ascii=False) + '\n话题：' + self.c['topic']))
        save(path, selected)
        return rules_for(selected)

    def api(self, route, payload=None):
        key = self.credential()
        if not key:
            raise ValueError('provide API key via --key-stdin or ARK_API_KEY')
        url = self.c['ark'].get('base_url', BASE_URL).rstrip('/') + route
        request = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)

    def text(self, prompt, model=None):
        model = model or self.c['ark']['text_model']
        if not model or not self.credential():
            raise ValueError('configure text_model and provide API key')
        if self.state['text_calls'] >= self.c['budget']['max_text_calls']:
            raise ValueError('text call budget exhausted')
        self.state['text_calls'] += 1
        self.persist()
        result = self.api('/chat/completions', {'model': model, 'messages': [{'role': 'system', 'content': '你是专业普通话短剧编剧和导演。只输出合法JSON，不要代码围栏。原创，保持系列人物与因果一致。'}, {'role': 'user', 'content': prompt}], 'stream': False})
        if result['choices'][0].get('finish_reason') == 'length':
            raise ValueError('model output truncated; reduce shot complexity before retry')
        content = result['choices'][0]['message']['content'].strip()
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\s*|\s*```$', '', content)
        return json.loads(content)

    def checked_text(self, prompt, validator, tag, model=None):
        key = digest(tag)
        limit = 1 + self.quality.get('max_structure_retries', 1)
        attempts = self.state.setdefault('structure_attempts', {}).get(key, 0)
        correction = ''
        while attempts < limit:
            attempts += 1
            self.state['structure_attempts'][key] = attempts
            self.persist()
            try:
                value = self.text(prompt + correction, model=model) if model else self.text(prompt + correction)
            except json.JSONDecodeError:
                correction = '\n上次返回无法解析为JSON。只返回合法JSON，不要代码围栏或额外文字。'
                continue
            try:
                validator(value)
                return value
            except (ValueError, KeyError, TypeError) as error:
                save(self.out / 'invalid-drafts' / f'{key}-{attempts}.json', value)
                correction = '\n上次结构/时间检查失败：' + str(error) + '。按原任务重写完整JSON并修复该问题。上次候选：' + json.dumps(value, ensure_ascii=False)
        raise ValueError('bounded structure retries exhausted; inspect invalid-drafts and start a corrected run')

    def durations(self):
        total = self.c['minutes_per_episode'] * 60
        d = self.c['ark']['video_options']['duration']
        return [min(d, total - i * d) for i in range(math.ceil(total / d))]

    def plan(self):
        c = self.c
        shots = len(self.durations()) * c['episodes'] * len(c['languages'])
        seconds = shots * c['ark']['video_options']['duration']
        classify = int(c.get('genre') == 'auto' and not self.brief.get('genre'))
        calls = 1 + classify + c['episodes'] * (1 + sum(x != c['source_language'] for x in c['languages']))
        review_languages = len(set(c['languages']) | {c['source_language']})
        revisions = self.quality.get('max_revisions', 2)
        translations = sum(x != c['source_language'] for x in c['languages'])
        maximum_calls = (calls + (c['episodes'] * (review_languages * (1 + 2 * revisions) + revisions * translations) if self.review_required else 0)) * (1 + self.quality.get('max_structure_retries', 1))
        b = c['budget']
        known = all(b.get(x) is not None for x in ['text_call_estimate_cny', 'video_second_estimate_cny'])
        value = {'episodes': c['episodes'], 'minutes_per_episode': c['minutes_per_episode'], 'languages': c['languages'], 'genre': self.brief.get('genre', c.get('genre', 'general')), 'review_required': self.review_required, 'shots': shots, 'submitted_video_seconds': seconds, 'estimated_text_calls': calls, 'maximum_planned_text_calls': maximum_calls, 'estimated_cny': maximum_calls * b['text_call_estimate_cny'] + seconds * b['video_second_estimate_cny'] if known else None, 'within_call_limits': maximum_calls <= b['max_text_calls'] and seconds <= b['max_video_seconds'], 'missing': [x for x in ['text_model', 'video_model'] if not c['ark'].get(x)], 'platform_upload_implemented': False}
        save(self.out / 'plan.json', value)
        return value

    def check_script(self, script, language=None):
        shots = script['shots']
        ds = self.durations()
        if len(shots) != len(ds):
            raise ValueError('script shot count differs from timeline')
        for i, (s, d) in enumerate(zip(shots, ds), 1):
            if s['id'] != i or abs(float(s['seconds']) - d) > .01:
                raise ValueError('shot IDs/durations must match timeline')
            if not s.get('visual') or not isinstance(s.get('dialogue'), str) or not isinstance(s.get('characters'), list):
                raise ValueError('each shot requires visual, dialogue string and characters')
            if not s['dialogue'] and s.get('audio_kind') != 'ambience':
                raise ValueError('empty dialogue requires ambience audio_kind')
            if self.review_required:
                if speech_seconds(s['dialogue'], language or self.c['source_language'], self.quality.get('han_per_second', 3.5)) > max(.1, d - .2):
                    raise ValueError('dialogue exceeds planning speech budget at shot ' + str(i))
        if self.review_required:
            if script.get('schema_version') != 2:
                raise ValueError('quality production requires script schema_version=2; regenerate legacy drafts')
            story = script.get('story', {})
            if any(not isinstance(story.get(k), str) or not story[k].strip() for k in ['goal', 'obstacle', 'strategy', 'choice', 'consequence', 'payoff', 'hook']):
                raise ValueError('story requires goal, obstacle, strategy, choice, consequence, payoff and hook')
            if not isinstance(script.get('clues'), list):
                raise ValueError('script requires clue ledger, which may be empty')
            bible_path = self.out / 'bible.json'
            if bible_path.exists():
                bible = read(bible_path)
                known = {x['id'] for x in bible['characters']}
                scenes = {x['id'] for x in bible.get('locations', []) if isinstance(x, dict)}
                for s in shots:
                    if scenes and s.get('scene_id') not in scenes:
                        raise ValueError('shot references unknown scene_id')
                    if not set(s['characters']) <= known or s.get('speaker') not in known | {'narrator', 'none'}:
                        raise ValueError('shot references unknown character/speaker')
                    if s.get('speaker') in known and s['speaker'] not in s['characters']:
                        raise ValueError('character speaker must be in this shot')
                clue_ids = {x['id'] for x in bible.get('clues', [])}
                if any(x.get('id') not in clue_ids or x.get('action') not in ['plant', 'advance', 'payoff'] for x in script['clues']):
                    raise ValueError('script clue event must reference bible clue IDs')
            for s in shots:
                if not s.get('scene_id') or not s.get('purpose') or s.get('audio_kind') not in ['dialogue', 'voiceover', 'ambience']:
                    raise ValueError('quality shots require scene_id, purpose and audio_kind')
                if s['audio_kind'] == 'ambience' and (s['dialogue'] or s.get('speaker') != 'none'):
                    raise ValueError('ambience shot must have empty dialogue and speaker=none')

    def check_bible(self, bible):
        if len(bible.get('episode_arcs', [])) != self.c['episodes'] or not bible.get('characters'):
            raise ValueError('incomplete story bible')
        if not self.review_required:
            return
        if bible.get('schema_version') != 2:
            raise ValueError('quality production requires bible schema_version=2')
        arcs = bible['episode_arcs']
        if [x.get('episode') for x in arcs] != list(range(1, self.c['episodes'] + 1)) or any(not all(x.get(k) for k in ['goal', 'obstacle', 'choice', 'consequence', 'payoff', 'hook']) for x in arcs):
            raise ValueError('bible requires causal tasks for every episode')
        chars = bible['characters']
        if len({x.get('id') for x in chars}) != len(chars) or any(not all(x.get(k) for k in ['id', 'name', 'appearance', 'costume', 'voice', 'motivation']) for x in chars):
            raise ValueError('bible requires unique character IDs and fixed production descriptions')
        if 'locations' in bible:
            locations = bible['locations']
            if not isinstance(locations, list) or not locations or any(not isinstance(x, dict) or not all(x.get(k) for k in ['id', 'description', 'lighting', 'props', 'axis']) for x in locations) or len({x['id'] for x in locations}) != len(locations):
                raise ValueError('locations require unique IDs, description, lighting, props and axis')
        clues = bible.get('clues')
        if not isinstance(clues, list) or len({x.get('id') for x in clues}) != len(clues):
            raise ValueError('bible requires unique clue ledger')
        for clue in clues:
            intro, resolved = clue.get('introduced_episode'), clue.get('resolved_episode')
            if not clue.get('id') or type(intro) is not int or type(resolved) is not int or not 1 <= intro <= resolved <= self.c['episodes'] or not clue.get('meaning'):
                raise ValueError('each clue requires valid setup/payoff episodes and meaning')

    def check_episode_clues(self, episode, script):
        if not self.review_required:
            return
        bible = read(self.out / 'bible.json')
        events = script['clues']
        ids = {x['id'] for x in script['shots']}
        if any(x.get('shot_id') not in ids for x in events):
            raise ValueError('clue events must reference actual shot_id')
        for clue in bible.get('clues', []):
            matches = [x for x in events if x['id'] == clue['id']]
            if clue['introduced_episode'] == episode and not any(x['action'] == 'plant' for x in matches):
                raise ValueError('scheduled clue setup missing in episode ' + str(episode))
            if clue['resolved_episode'] == episode and not any(x['action'] == 'payoff' for x in matches):
                raise ValueError('scheduled clue payoff missing in episode ' + str(episode))
            if any(x['action'] == 'plant' and clue['introduced_episode'] != episode or x['action'] == 'payoff' and clue['resolved_episode'] != episode for x in matches):
                raise ValueError('clue event conflicts with planned setup/payoff episode')

    def pin_script(self, key, script):
        hashes = self.state.setdefault('script_hashes', {})
        current = digest(script)
        if key in hashes and hashes[key] != current:
            raise ValueError('script changed after production began: use a new run directory')
        hashes[key] = current
        self.persist()

    def write(self, episodes):
        c = self.c
        rules = self.genre_rules()
        bp = self.out / 'bible.json'
        if not bp.exists():
            brief = self.brief
            bible = self.checked_text('按选定主类型规则创作完整系列圣经，不默认男频或隐藏富豪。JSON字段schema_version=2,title,premise,characters(每项id,name,appearance,costume,voice,motivation),locations(非空数组，每项id,description,lighting,props,axis用于固定场景空间),episode_arcs(每项episode,goal,obstacle,choice,consequence,payoff,hook),clues(数组，每项id,meaning,introduced_episode,resolved_episode；无伏笔可为空),continuity。每集任务有因果，最终集兑现主线与伏笔。所有 ' + str(c['episodes']) + ' 集都有明确规划。\n' + json.dumps({'config': c, 'director_brief': brief, 'genre_rules': rules}, ensure_ascii=False), self.check_bible, 'bible')
            self.check_bible(bible)
            save(bp, bible)
        bible = read(bp)
        self.check_bible(bible)
        for ep in episodes:
            folder = self.out / f'ep{ep:03d}'
            src = folder / 'source.json'
            if not src.exists():
                previous = self.out / f'ep{ep-1:03d}' / 'source.json'
                if ep > 1 and not previous.exists():
                    raise ValueError('write preceding episode first for continuity')
                prompt = {'bible': bible, 'director_brief': self.brief, 'genre_rules': rules, 'previous_episode': read(previous) if previous.exists() else None, 'episode': ep, 'language': c['source_language'], 'style': c['style'], 'shot_durations': self.durations(), 'speech_budget': '普通话每秒约' + str(self.quality.get('han_per_second', 3.5)) + '字且预留停顿；对白宁短勿抢，单镜一个说话人，允许无台词环境镜头。'}
                script = self.checked_text('创作指定集可拍分镜。JSON schema_version=2,title,synopsis,story(含goal,obstacle,strategy,choice,consequence,payoff,hook),clues(数组，每项id为圣经线索ID，action为plant/advance/payoff，shot_id为实际镜头；按圣经计划在指定集种下/回收，不能提前或遗忘),shots。每镜id连续从1,seconds严格按shot_durations,characters固定ID数组,scene_id,purpose(本镜叙事作用),visual(画面/动作/运镜),audio_kind(dialogue/voiceover/ambience),speaker(人物ID/narrator/none),dialogue(只含说出的台词，不含人名标签；ambience时空字符串)。重要选择和结果要有实际镜头，避免画面内文字。只输出本集。\n' + json.dumps(prompt, ensure_ascii=False), lambda x: (self.check_script(x), self.check_episode_clues(ep, x)), f'source/{ep}')
                self.check_script(script)
                self.check_episode_clues(ep, script)
                save(src, script)
            source = read(src)
            self.check_script(source)
            self.check_episode_clues(ep, source)
            for lang in c['languages']:
                target = folder / lang / 'script.json'
                if target.exists():
                    self.check_script(read(target), lang)
                    continue
                localized = source if lang == c['source_language'] else self.text('本地化到 ' + lang + '。保留schema_version=2、story事件、clues、人物ID、shots的id,seconds,characters,speaker,audio_kind与事件顺序；本地化title,synopsis,dialogue以及visual的语言说明，口语适应时长。返回相同完整JSON结构。\n' + json.dumps(source, ensure_ascii=False))
                self.check_script(localized, lang)
                save(target, localized)
                self.state.setdefault('localization_sources', {})[f'{ep}/{lang}'] = digest(source)
                self.persist()
        return {'status': 'scripts_ready', 'episodes': episodes}

    def review_script(self, episode, language, path, rules):
        report_path = self.out / f'ep{episode:03d}' / language / 'review.json'
        key = f'{episode}/{language}'
        while True:
            script = read(path)
            draft_zero = report_path.parent / 'drafts' / '000-original.json'
            if not draft_zero.exists():
                save(draft_zero, script)
            self.check_script(script, language)
            self.check_episode_clues(episode, script)
            bible = read(self.out / 'bible.json')
            self.check_bible(bible)
            previous = self.out / f'ep{episode-1:03d}' / 'source.json'
            context = {'script': script, 'bible': bible, 'previous_episode': read(previous) if previous.exists() else None, 'director_brief': self.brief, 'genre_rules': rules, 'language': language}
            signature = digest({'context': context, 'minimum': self.quality.get('minimum_score', 16)})
            cached = read(report_path) if report_path.exists() else {}
            if cached.get('review_input_sha256') == signature:
                report = cached
            else:
                prompt = '作为严格编辑审查，不预测流量。评估人物动机、因果、每集任务、情绪兑现、伏笔与最终集收束，以及主类型要求。输出JSON scores(以下十维各0..2):' + json.dumps(rules['common']['dimensions']) + '，dimension_evidence(同名十维各含reason与真实shot_ids)，genre_checks(逐条评估主类型review_checks，criterion为原文，pass布尔,reason,shot_ids)，issues(数组，每项severity=blocker/major/minor,reason,repair,shot_ids)。优点也必须给真实镜头证据；不能因格式齐全就打满分。\n' + json.dumps(context, ensure_ascii=False)
                report = self.checked_text(prompt, lambda x: review_verdict(x, script, rules, self.quality.get('minimum_score', 16)), 'review/' + signature, model=self.c['ark'].get('review_model'))
            verdict = review_verdict(report, script, rules, self.quality.get('minimum_score', 16))
            report.update(verdict, review_input_sha256=signature, script_sha256=digest(script), reviewer_model=self.c['ark'].get('review_model') or self.c['ark']['text_model'], independent_model=bool(self.c['ark'].get('review_model') and self.c['ark']['review_model'] != self.c['ark']['text_model']))
            save(report_path, report)
            if verdict['passed']:
                return {'status': 'editorial_pass', 'episode': episode, 'language': language}
            revisions = self.state.setdefault('review_revisions', {}).get(key, 0)
            if revisions >= self.quality.get('max_revisions', 2):
                return {'status': 'review_failed', 'episode': episode, 'language': language, 'report': str(report_path), 'video_not_submitted': True}
            shots_folder = report_path.parent / 'shots'
            if key in self.state.get('script_hashes', {}) or any(x.startswith(key + '/') for x in self.state['tasks']) or (shots_folder.exists() and any(shots_folder.glob('*.mp4'))):
                raise ValueError('cannot rewrite after media production; use a new run directory')
            self.state['review_revisions'][key] = revisions + 1
            self.persist()
            revised = self.checked_text('按审稿具体意见重写本集，保持JSON v2、人物ID、线索ID、镜头编号数量和每镜时长；不变更系列总目标、关键事件与下集必须承接的状态，改善动机铺垫、动作呈现和对白。不要复制案例情节。输出完整剧本JSON。\n' + json.dumps({'context': context, 'review': report}, ensure_ascii=False), lambda x: (self.check_script(x, language), self.check_episode_clues(episode, x)), f'revision/{key}/{revisions+1}')
            save(report_path.parent / 'drafts' / f'{revisions+1:03d}-revision.json', revised)
            self.check_script(revised, language)
            self.check_episode_clues(episode, revised)
            save(path, revised)

    def review(self, episodes):
        if not self.review_required:
            return {'status': 'review_disabled', 'assessment': 'not_editorially_verified'}
        rules = self.genre_rules()
        for ep in episodes:
            folder = self.out / f'ep{ep:03d}'
            source_path = folder / 'source.json'
            before = digest(read(source_path))
            result = self.review_script(ep, self.c['source_language'], source_path, rules)
            if result['status'] == 'review_failed':
                return result
            source = read(source_path)
            source_changed = before != digest(source)
            for lang in self.c['languages']:
                target = folder / lang / 'script.json'
                if lang == self.c['source_language']:
                    save(target, source)
                    continue
                if source_changed or self.state.get('localization_sources', {}).get(f'{ep}/{lang}') != digest(source):
                    key = f'{ep}/{lang}'
                    if key in self.state.get('script_hashes', {}) or any(x.startswith(key + '/') for x in self.state['tasks']):
                        raise ValueError('source revised after localized production; use a new run directory')
                    localized = self.text('根据已审定源剧本重新本地化到 ' + lang + '，保持schema_version=2与story事件顺序、人物/线索ID、镜头编号及时长，只调整表达。返回完整同结构JSON。\n' + json.dumps(source, ensure_ascii=False))
                    self.check_script(localized, lang)
                    save(target, localized)
                    self.state.setdefault('localization_sources', {})[f'{ep}/{lang}'] = digest(source)
                    self.persist()
                result = self.review_script(ep, lang, target, rules)
                if result['status'] == 'review_failed':
                    return result
        return {'status': 'editorial_pass', 'episodes': episodes, 'assessment': 'not_virality_prediction'}

    def require_review(self, episode, language, script):
        if not self.review_required:
            return
        report_path = self.out / f'ep{episode:03d}' / language / 'review.json'
        if not report_path.exists():
            raise ValueError('run review before video generation')
        report = read(report_path)
        rules = self.genre_rules()
        bible = read(self.out / 'bible.json')
        previous = self.out / f'ep{episode-1:03d}' / 'source.json'
        context = {'script': script, 'bible': bible, 'previous_episode': read(previous) if previous.exists() else None, 'director_brief': self.brief, 'genre_rules': rules, 'language': language}
        signature = digest({'context': context, 'minimum': self.quality.get('minimum_score', 16)})
        verdict = review_verdict(report, script, rules, self.quality.get('minimum_score', 16))
        if not verdict['passed'] or report.get('script_sha256') != digest(script) or report.get('review_input_sha256') != signature:
            raise ValueError('script review missing, failed or stale; no video submitted')

    def video(self, episodes):
        c = self.c
        jobs = []
        for ep in episodes:
            for lang in c['languages']:
                folder = self.out / f'ep{ep:03d}' / lang
                script = read(folder / 'script.json')
                self.check_script(script, lang)
                self.require_review(ep, lang, script)
                self.pin_script(f'{ep}/{lang}', script)
                for shot in script['shots']:
                    path = folder / 'shots' / f"{shot['id']:03d}.mp4"
                    if path.exists():
                        continue
                    k = f"{ep}/{lang}/{shot['id']}"
                    record = self.state['tasks'].get(k)
                    if record is not None and 'id' not in record:
                        raise ValueError('unknown submission; reconcile supplier task list before retry: ' + k)
                    if record is not None and record['status'] in ['failed', 'cancelled', 'expired']:
                        raise ValueError('video task terminal failure; inspect supplier before explicit retry: ' + k)
                    jobs.append((k, path, shot, lang, record))
        if not jobs:
            return {'status': 'all_shots_available'}
        pending = [x for x in jobs if x[4] is not None]
        unsubmitted = [x for x in jobs if x[4] is None]
        limit = c.get('execution', {}).get('max_inflight_video_tasks', 1)
        if unsubmitted and len(pending) < limit:
            job = unsubmitted[0]
        else:
            cursor = self.state.get('poll_cursor', 0)
            job = pending[cursor % len(pending)]
            self.state['poll_cursor'] = cursor + 1
            self.persist()
        return self.process_video_job(*job)

    def process_video_job(self, k, path, shot, lang, record):
        c = self.c
        if record is None:
            if not c['ark'].get('video_model') or not self.credential():
                raise ValueError('configure video_model and provide API key')
            refs = reference_content(self.assets, k, c.get('assets', {}))
            d = c['ark']['video_options']['duration']
            if self.state['video_seconds'] + d > c['budget']['max_video_seconds']:
                raise ValueError('video generation budget exhausted')
            self.state['video_seconds'] += d
            self.state['tasks'][k] = {'status': 'unknown_submission'}
            self.persist()
            bible_path = self.out / 'bible.json'
            bible = read(bible_path) if bible_path.exists() else {}
            characters = [x for x in bible.get('characters', []) if x.get('id') in shot['characters']]
            locations = bible.get('locations', [])
            location = next((x for x in locations if isinstance(x, dict) and x.get('id') == shot.get('scene_id')), None) if isinstance(locations, list) else None
            script = read(path.parent.parent / 'script.json')
            adjacent = [x for x in script['shots'] if abs(x['id'] - shot['id']) == 1]
            continuity = {'scene': location, 'series_rules': bible.get('continuity'), 'adjacent_shots': [{'id': x['id'], 'scene_id': x.get('scene_id'), 'visual': x['visual']} for x in adjacent]}
            audio = ('声音：无台词，自然环境音。' if shot.get('audio_kind') == 'ambience' else '对白语言：' + lang + ('，使用标准普通话。' if lang == 'zh-CN' else '。') + '说话人：' + shot.get('speaker', 'narrator') + '；只说以下对白：' + shot['dialogue'])
            prompt = c['style'] + '\n固定角色设定：' + json.dumps(characters, ensure_ascii=False) + '\n连续性参考：' + json.dumps(continuity, ensure_ascii=False) + '\n同场景保持道具位置、光线和人物视线轴线；只生成当前镜头，不把相邻镜头重复拍进本镜。\n叙事作用：' + shot.get('purpose', '') + '\n' + shot['visual'] + '\n' + audio
            result = self.api('/contents/generations/tasks', {'model': c['ark']['video_model'], **c['ark']['video_options'], 'content': [{'type': 'text', 'text': prompt}, *refs]})
            task_id = result['id']
            if not re.fullmatch(r'[A-Za-z0-9_-]+', task_id):
                raise ValueError('invalid task ID')
            self.state['tasks'][k] = {'status': 'submitted', 'id': task_id}
            self.persist()
            return {'shot': k, 'status': 'submitted', 'next': 'run video again later'}
        result = self.api('/contents/generations/tasks/' + record['id'])
        record['status'] = result['status']
        self.persist()
        if result['status'] == 'succeeded':
            url = result['content']['video_url']
            if urlparse(url).scheme != 'https':
                raise ValueError('download URL must be HTTPS')
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix('.download')
            with urllib.request.urlopen(url, timeout=45) as response, tmp.open('wb') as f:
                while chunk := response.read(1024 * 1024):
                    f.write(chunk)
            if not any(x['codec_type'] == 'video' for x in self.probe(tmp)['streams']):
                raise ValueError('supplier download did not contain video; retained temporary file')
            tmp.replace(path)
            return {'shot': k, 'status': 'downloaded'}
        if result['status'] in ['failed', 'cancelled', 'expired']:
            raise ValueError('video task terminal failure; inspect supplier before explicit retry: ' + k)
        return {'shot': k, 'status': result['status'], 'next': 'poll later'}

    @staticmethod
    def probe(path):
        return json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)], text=True, encoding='utf-8'))

    def render(self, episodes):
        r = self.c['render']
        for ep in episodes:
            for lang in self.c['languages']:
                folder = self.out / f'ep{ep:03d}' / lang
                script = read(folder / 'script.json')
                self.check_script(script, lang)
                self.pin_script(f'{ep}/{lang}', script)
                clips, subtitles, start = [], [], 0.0
                for shot in script['shots']:
                    path = folder / 'shots' / f"{shot['id']:03d}.mp4"
                    probe = self.probe(path)
                    d = shot['seconds']
                    if float(probe['format']['duration']) + .1 < d or not any(x['codec_type'] == 'video' for x in probe['streams']):
                        raise ValueError('missing/short video: ' + str(path))
                    wav = path.with_suffix('.wav')
                    audio = wav if wav.exists() else path
                    ap = self.probe(audio)
                    streams = [x for x in ap['streams'] if x['codec_type'] == 'audio']
                    if not streams or float(streams[0].get('duration', ap['format']['duration'])) + .1 < d:
                        raise ValueError('missing/short voice track: ' + str(audio))
                    clip = folder / 'render' / f"{shot['id']:03d}.mkv"
                    clip.parent.mkdir(parents=True, exist_ok=True)
                    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', str(path)]
                    if wav.exists():
                        cmd += ['-i', str(wav)]
                    cmd += ['-map', '0:v:0', '-map', '1:a:0' if wav.exists() else '0:a:0', '-t', str(d), '-vf', f"scale={r['width']}:{r['height']}:force_original_aspect_ratio=decrease,pad={r['width']}:{r['height']}:(ow-iw)/2:(oh-ih)/2,setsar=1", '-r', str(r['fps']), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', str(clip)]
                    subprocess.run(cmd, check=True)
                    clips.append(clip.name)
                    if shot['dialogue']:
                        subtitles.append(f"{len(subtitles)+1}\n{stamp(start)} --> {stamp(start+d)}\n{shot['dialogue']}\n")
                    start += d
                concat = folder / 'render' / 'concat.txt'
                concat.write_text(''.join(f"file '{name}'\n" for name in clips), encoding='utf-8')
                master = folder / 'master.mp4'
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '1', '-i', str(concat), '-c:v', 'copy', '-c:a', 'aac', '-movflags', '+faststart', str(master)], check=True)
                actual = float(self.probe(master)['format']['duration'])
                if abs(actual - start) > .5:
                    raise ValueError('render duration outside tolerance')
                (folder / 'captions.srt').write_text('\n'.join(subtitles), encoding='utf-8')
                save(folder / 'qc.json', {'duration': actual, 'target': start, 'script_sha256': digest(script), 'media_inputs_sha256': digest(media_signature(folder, script, r)), 'master_stat': {'size': master.stat().st_size, 'mtime_ns': master.stat().st_mtime_ns}, 'mechanical_pass': True, 'voice_reviewed': False, 'visual_reviewed': False, 'subtitle_aligned': False})
        return {'status': 'rendered_pending_human_review'}

    def package(self):
        rows = []
        for ep in range(1, self.c['episodes'] + 1):
            for lang in self.c['languages']:
                folder = self.out / f'ep{ep:03d}' / lang
                sp = folder / 'script.json'
                script = read(sp) if sp.exists() else {}
                master = folder / 'master.mp4'
                qc = read(folder / 'qc.json') if (folder / 'qc.json').exists() else None
                master_stat = {'size': master.stat().st_size, 'mtime_ns': master.stat().st_mtime_ns} if master.exists() else None
                media_current = bool(master.exists() and qc and qc.get('script_sha256') == digest(script) and qc.get('media_inputs_sha256') == digest(media_signature(folder, script, self.c['render'])) and qc.get('master_stat') == master_stat)
                review = read(folder / 'review.json') if (folder / 'review.json').exists() else None
                asset_hash = file_sha256(master) if master.exists() else None
                for platform in self.c['platforms']:
                    rows.append({'platform': platform, 'episode': ep, 'language': lang, 'title': script.get('title'), 'synopsis': script.get('synopsis'), 'video': str(master.resolve()), 'subtitle': str((folder / 'captions.srt').resolve()), 'media_exists': master.exists(), 'media_current': media_current, 'asset_sha256': asset_hash, 'qc': qc, 'script_review': {'passed': review.get('passed'), 'assessment': review.get('assessment')} if review else None, 'rights': self.c['rights'], 'filing': self.c['filing'], 'access': self.c.get('platform_access', {}).get(platform, 'not_connected'), 'status': 'prepared' if media_current else ('stale_or_unverified_media' if master.exists() else 'missing_media'), 'published': False})
        save(self.out / 'publish-manifest.json', rows)
        return {'status': 'package_created', 'rows': len(rows), 'uploaded': False}

    def run(self, episodes):
        for ep in episodes:
            self.write([ep])
            review = self.review([ep])
            if review['status'] == 'review_failed':
                return {'stage': 'script_review', **review}
            progress = self.video([ep])
            if progress['status'] != 'all_shots_available':
                return {'stage': 'video', **progress}
            complete = True
            for lang in self.c['languages']:
                folder = self.out / f'ep{ep:03d}' / lang
                qc = read(folder / 'qc.json') if (folder / 'qc.json').exists() else {}
                script = read(folder / 'script.json')
                master = folder / 'master.mp4'
                current_stat = {'size': master.stat().st_size, 'mtime_ns': master.stat().st_mtime_ns} if master.exists() else None
                complete = complete and master.exists() and qc.get('mechanical_pass') and qc.get('script_sha256') == digest(script) and qc.get('media_inputs_sha256') == digest(media_signature(folder, script, self.c['render'])) and qc.get('master_stat') == current_stat
            if not complete:
                self.render([ep])
        return {'stage': 'review', 'episodes': episodes, **self.package()}


def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'


def main():
    for stream in [sys.stdout, sys.stderr]:
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['plan', 'genres', 'write', 'review', 'video', 'render', 'package', 'run'])
    parser.add_argument('--config', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--episode', type=int)
    parser.add_argument('--key-stdin', action='store_true', help='read session API key from first stdin line; never save it')
    parser.add_argument('--until-ready', action='store_true', help='advance run until review checkpoint or finite step limit')
    parser.add_argument('--max-steps', type=int, default=300)
    parser.add_argument('--poll-seconds', type=float, default=10)
    args = parser.parse_args()
    if args.until_ready and args.command != 'run' or not 1 <= args.max_steps <= 10000 or not 1 <= args.poll_seconds <= 60:
        parser.error('until-ready requires run; max-steps 1..10000; poll-seconds 1..60')
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    lock = out / '.run.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError('run already active; inspect process before clearing stale lock')
    os.close(fd)
    try:
        session_key = read_session_key(sys.stdin) if args.key_stdin else None
        p = Pipeline(read(args.config), out, api_key=session_key)
        if args.episode is not None and not 1 <= args.episode <= p.c['episodes']:
            raise ValueError('episode outside configured range')
        episodes = [args.episode] if args.episode is not None else list(range(1, p.c['episodes'] + 1))
        for step in range(args.max_steps if args.until_ready else 1):
            result = getattr(p, args.command)() if args.command in ['plan', 'genres', 'package'] else getattr(p, args.command)(episodes)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if not args.until_ready or result.get('stage') != 'video':
                break
            if result['status'] not in ['submitted', 'downloaded']:
                time.sleep(args.poll_seconds)
        else:
            print(json.dumps({'status': 'step_limit_reached', 'resume': True}), flush=True)
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # Provider response bodies and URL query strings may contain private data.
        print('Stopped: ' + (str(e) if isinstance(e, (ValueError, FileNotFoundError)) else type(e).__name__), file=sys.stderr)
        sys.exit(1)
