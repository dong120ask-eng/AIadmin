"""TOP read-only adapter. Credentials are resolved only from environment."""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

FIELDS = ('tenant_id', 'platform', 'store_id', 'target_id', 'action', 'idempotency_key')
ENDPOINT = 'https://eco.taobao.com/router/rest'

class Blocked(Exception):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise Blocked('redirect_blocked')

def sign(params, secret):
    value = secret + ''.join(k + params[k] for k in sorted(params) if k != 'sign') + secret
    return hashlib.md5(value.encode()).hexdigest().upper()

class Client:
    def __init__(self, key, secret, session):
        self.key, self.secret, self.session = key, secret, session
        self.evidence = []

    def call(self, method, **params):
        allowed = {'taobao.shop.seller.get', 'taobao.items.onsale.get'}
        if method not in allowed:
            raise Blocked('method_not_allowed')
        public = dict(params)
        params.update(method=method, app_key=self.key, session=self.session,
                      timestamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
                      format='json', v='2.0', sign_method='md5')
        params['sign'] = sign(params, self.secret)
        request = Request(ENDPOINT, urlencode(params).encode(),
                          {'Content-Type': 'application/x-www-form-urlencoded;charset=utf-8'})
        try:
            with build_opener(NoRedirect()).open(request, timeout=15) as response:
                raw = response.read(800001)
                if len(raw) > 800000:
                    raise Blocked('response_too_large')
                payload = json.loads(raw)
        except Blocked:
            raise
        except Exception:
            raise Blocked('transport_or_json_error') from None
        entry = {'method': method, 'parameters': public, 'endpoint': ENDPOINT,
                 'response_sha256': hashlib.sha256(raw).hexdigest(),
                 'observed_at': datetime.now(timezone.utc).isoformat()}
        self.evidence.append(entry)
        if not isinstance(payload, dict):
            raise Blocked('invalid_response')
        if 'error_response' in payload:
            # Never echo platform messages: they may contain request credentials.
            entry['platform_error'] = True
            raise Blocked('platform_rejected_request')
        root = method.removeprefix('taobao.').replace('.', '_') + '_response'
        result = payload.get(root)
        if not isinstance(result, dict):
            raise Blocked('missing_response_envelope')
        return result

def run(req, binding, client):
    if req.get('op') != 'read' or req.get('action') != 'product_read':
        raise Blocked('unsupported_read_capability_or_write')
    if any(not isinstance(req.get(k), str) or not req[k] for k in FIELDS):
        raise Blocked('missing_scope')
    if req['platform'] not in ('taobao', 'tmall') or any(req[k] != binding.get(k) for k in ('tenant_id', 'platform', 'store_id')):
        raise Blocked('binding_mismatch')
    if req['target_id'] != 'onsale':
        raise Blocked('only_onsale_collection_supported')
    shop = client.call('taobao.shop.seller.get', fields='sid,title').get('shop', {})
    if not shop.get('sid') or str(shop['sid']) != binding.get('shop_sid'):
        raise Blocked('remote_shop_identity_mismatch')
    items = []
    total = None
    for page in range(1, 6):
        result = client.call('taobao.items.onsale.get', fields='num_iid,title,price,num,approve_status',
                             page_no=str(page), page_size='40')
        current_total = result.get('total_results')
        if isinstance(current_total, bool) or not isinstance(current_total, int) or current_total < 0:
            raise Blocked('invalid_total')
        if total is not None and current_total != total:
            raise Blocked('catalog_changed_retry_manually')
        total = current_total
        batch = result.get('items', {}).get('item', [])
        if not isinstance(batch, list) or len(batch) > 40:
            raise Blocked('invalid_items')
        for item in batch:
            if not isinstance(item, dict) or not item.get('num_iid'):
                raise Blocked('invalid_item')
            items.append({k: item[k] for k in ('num_iid', 'title', 'price', 'num', 'approve_status') if k in item})
        if len(items) >= total:
            break
        if not batch:
            raise Blocked('incomplete_page')
    ids = [str(i['num_iid']) for i in items]
    if len(set(ids)) != len(ids) or len(items) > total:
        raise Blocked('inconsistent_pagination')
    return dict({k: req[k] for k in FIELDS}, ok=True, observed_at=datetime.now(timezone.utc).isoformat(),
                value={'shop_sid': str(shop['sid']), 'items': items, 'total_results': total,
                       'complete': len(items) == total, 'source': 'official_top_api',
                       'scope': 'onsale_only', 'snapshot_atomic': False}, evidence=client.evidence)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--binding', required=True)
    parser.add_argument('--data-output', help='New private output path; never overwrite')
    args = parser.parse_args()
    req = {}
    try:
        req = json.loads(sys.stdin.read(16000))
        with open(args.binding, encoding='utf-8') as f:
            binding = json.load(f)
        names = binding['credential_env']
        credentials = [os.environ[names[k]] for k in ('app_key', 'app_secret', 'session')]
        if not all(credentials):
            raise Blocked('missing_credentials')
        result = run(req, binding, Client(*credentials))
        if args.data_output:
            fd = os.open(args.data_output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                json.dump(result, output, ensure_ascii=False)
    except Blocked as error:
        result = {'ok': False, 'reason': str(error)}
    except Exception:
        result = {'ok': False, 'reason': 'invalid_configuration_or_request'}
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
