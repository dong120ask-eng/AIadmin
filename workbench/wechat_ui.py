"""Opt-in Playwright UI port. No automatic installation, login or publishing.

Selectors are account/UI-version-specific and MUST be captured on the official
page by an authorized operator. No guessed production selectors are shipped.
This module is not exercised against WeChat in the cloud environment.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from .store import Problem


class WechatBrowserUI:
    verification_mode = 'official_browser'
    REQUIRED = {'identity','new_article','title','body','save','draft_list',
                'draft_rows','row_title','row_open','draft_id','cover_input',
                'cover_confirm','cover_image','inline_input','inline_images'}

    def __init__(self, config, profiles_root):
        if (not isinstance(config,dict) or set(config) != {'profile_ref','selectors','ui_verified_at'}
                or not config['ui_verified_at'] or set(config['selectors']) != self.REQUIRED):
            raise Problem('须先在授权官方页面核验并配置全部选择器')
        from .store import identifier
        identifier(config['profile_ref'])
        if not all(isinstance(v,str) and 0 < len(v) <= 500 for v in config['selectors'].values()):
            raise Problem('选择器无效')
        self.config = config
        self.profile_dir = Path(profiles_root).resolve()/config['profile_ref']
        self.page = self.context = self.engine = None
        self.mapping = None
        self.profile_lease = None

    def _official(self):
        parts = urlsplit(self.page.url)
        if parts.scheme != 'https' or parts.hostname != 'mp.weixin.qq.com' or parts.port not in (None,443):
            raise Problem('当前页面不是公众号官方后台',409)

    def _one(self, key, root=None):
        self._official()
        node = (root or self.page).locator(self.config['selectors'][key])
        if node.count() != 1:raise Problem('页面版本变化或元素不唯一；停止执行',409)
        return node

    def connect(self, binding):
        if binding['profile_ref'] != self.config['profile_ref']:
            raise Problem('会话配置不匹配',409)
        from .wechat_session import open_profile
        self.profile_lease, self.engine, self.context, self.page = open_profile(self.profile_dir)
        # Login is performed beforehand in the SAME dedicated profile. A QR/login
        # wall causes identity() to fail BEFORE an editor is opened.
        self._official()

    def identity(self):
        node = self._one('identity')
        value = node.input_value() if node.evaluate('(e)=>e.matches("input,textarea")') else node.inner_text()
        return value.strip()

    def _click(self,key,guard,root=None):
        guard()
        self._one(key,root).click(timeout=10000)
        self._official()

    def _image_id(self,key):
        # Observed DOM data-id must identify the uploaded media, not a signed URL.
        value = self._one(key).get_attribute('data-id')
        if not value or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value):
            raise Problem('无法核对素材稳定ID',409)
        return value

    def fill(self, article, assets_root, guard):
        self._click('new_article',guard)
        guard();self._one('title').fill(article['title'])
        guard();self._one('body').fill(article['body'])
        # First version appends inline images in manifest order; no HTML/Markdown
        # rendering. Ambiguous placement is never silently treated as supported.
        self.mapping = {'cover':None,'inline':[]}
        for asset in article['assets']:
            role = asset['role'];guard()
            self._one('cover_input' if role=='cover' else 'inline_input').set_input_files(str(Path(assets_root)/asset['path']))
            if role == 'cover':
                self._click('cover_confirm',guard)
                self.mapping['cover'] = self._image_id('cover_image')
            else:
                nodes = self.page.locator(self.config['selectors']['inline_images'])
                expected = len(self.mapping['inline'])+1
                if nodes.count() != expected:raise Problem('正文图片上传结果不明确',409)
                value = nodes.nth(expected-1).get_attribute('data-id')
                if not value or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',value):
                    raise Problem('正文素材ID缺失',409)
                self.mapping['inline'].append(value)
        self.article = article

    def save_draft(self, guard):
        button = self._one('save')
        # Dedicated allowlist, independent of selector configuration.
        if button.inner_text().strip() not in {'保存草稿','保存为草稿','保存'}:
            raise Problem('目标控件不是草稿保存按钮',409)
        self._click('save',guard)  # exactly one click; no retry
        reference = self._one('draft_id').get_attribute('data-id')
        if not reference or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',reference):
            raise Problem('保存后草稿ID不明确，须人工核对',409)
        # Mapping is local evidence, persisted by export_receipt after save and
        # before leaving editor. Worker also persists reference in SQLite.
        self.receipt = {'draft_ref':reference,'mapping':self.mapping,'article':self.article}
        return reference

    def export_receipt(self):
        return getattr(self,'receipt',None)

    def restore_receipt(self, receipt):
        self.receipt = receipt
        self.mapping = receipt['mapping']
        self.article = receipt['article']

    def read_draft(self, reference):
        # Navigate through the visible draft list; do not reuse editor fields.
        self._one('draft_list').click(timeout=10000)
        self._official()
        rows = self.page.locator(self.config['selectors']['draft_rows'])
        matches = []
        for n in range(rows.count()):
            row = rows.nth(n)
            if row.get_attribute('data-id') == reference:matches.append(row)
        if len(matches) != 1:raise Problem('草稿列表未找到唯一的已保存记录',409)
        row = matches[0]
        if self._one('row_title',row).inner_text().strip() != self.article['title']:
            raise Problem('草稿列表标题不一致',409)
        self._one('row_open',row).click(timeout=10000)
        self._official()
        if self._one('draft_id').get_attribute('data-id') != reference:
            raise Problem('打开的草稿ID不一致',409)
        if self._image_id('cover_image') != self.mapping['cover']:
            raise Problem('封面素材与上传结果不一致',409)
        nodes = self.page.locator(self.config['selectors']['inline_images'])
        actual = [nodes.nth(n).get_attribute('data-id') for n in range(nodes.count())]
        if actual != self.mapping['inline']:raise Problem('正文素材丢失或顺序变化',409)
        return {'draft_ref':reference,'title':self._one('title').input_value(),
                'body':self._one('body').inner_text(),'assets':self.article['assets'],
                'account_unique_id':self.identity(),'reopened_from_list':True}

    def close(self):
        try:
            if self.context:self.context.close()
        finally:
            try:
                if self.engine:self.engine.stop()
            finally:
                if self.profile_lease:self.profile_lease.close()
