"""Local-only QR bootstrap. Never exports browser state or navigated URLs."""
import argparse
import json
import os
from pathlib import Path
from .store import Problem, identifier


class ProfileLease:
    """OS-held lock shared by login and worker; crash releases lock automatically."""
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.handle = None

    def acquire(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise Problem('会话目录不得为符号链接')
        handle = (self.directory / '.aiadmin-profile.lock').open('a+b')
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise Problem('专用浏览器会话正在使用；先关闭登录窗口或旧执行器', 409) from None
        self.handle = handle
        return self

    def close(self):
        if self.handle:
            self.handle.close(); self.handle = None


def open_profile(directory):
    lease = ProfileLease(directory).acquire()
    engine = context = None
    try:
        from playwright.sync_api import sync_playwright
        engine = sync_playwright().start()
        context = engine.chromium.launch_persistent_context(str(directory), headless=False)
        context.set_default_timeout(10000)
        page = context.new_page()
        page.goto('https://mp.weixin.qq.com/', timeout=20000)
        return lease, engine, context, page
    except Exception:
        if context: context.close()
        if engine: engine.stop()
        lease.close()
        raise Problem('浏览器启动或官方后台访问失败；检查本机运行时和网络，不自动重试') from None


def login(profiles_root, profile_ref, config=None, expected_id=None, inspect=False, prompt=input):
    identifier(profile_ref)
    if (config is None) != (expected_id is None):
        raise Problem('身份核验需要同时提供选择器配置与预期唯一账号ID')
    ui = None
    if config is not None:
        from .wechat_ui import WechatBrowserUI
        ui = WechatBrowserUI(config, profiles_root)
        if config['profile_ref'] != profile_ref or not expected_id.strip():
            raise Problem('登录会话或预期账号配置不匹配')
    directory = Path(profiles_root).resolve() / profile_ref
    lease, engine, context, page = open_profile(directory)
    try:
        from .wechat_ui import WechatBrowserUI
        check = ui or object.__new__(WechatBrowserUI)
        check.page = page
        check._official()
        prompt('仅在官方页面扫码并人工核对账号；完成后按回车。不要粘贴任何凭证：')
        check._official()
        verified = False
        if ui:
            if ui.identity() != expected_id.strip():
                raise Problem('页面唯一账号ID不匹配；禁止执行草稿', 409)
            verified = True
        if inspect:
            # Inspector is interactive and local. No trace, codegen or DOM export.
            page.pause()
            check._official()
            if ui and ui.identity() != expected_id.strip():
                raise Problem('检查期间账号发生变化', 409)
        return {'status': 'identity_checked' if verified else 'manual_login_only',
                'identity_verified': verified, 'draft_saved': False,
                'publishing_verified': False}
    finally:
        try: context.close()
        finally:
            try: engine.stop()
            finally: lease.close()


def main():
    p = argparse.ArgumentParser(description='公众号本机专用会话扫码；不填写、不保存、不发布')
    p.add_argument('--profiles-root', required=True)
    p.add_argument('--profile-ref', required=True)
    p.add_argument('--config')
    p.add_argument('--expected-id')
    p.add_argument('--inspect', action='store_true')
    args = p.parse_args()
    try:
        config = json.loads(Path(args.config).read_text(encoding='utf-8-sig')) if args.config else None
        print(json.dumps(login(args.profiles_root, args.profile_ref, config, args.expected_id, args.inspect), ensure_ascii=False))
        return 0
    except (Problem, OSError, ValueError, KeyboardInterrupt, EOFError):
        print('会话初始化或核验未完成；不记录登录成功，不执行草稿。请本机检查配置、运行时与官方页面。')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
