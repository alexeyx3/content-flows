"""Localized cover CLI cannot attach a same-slug EN record or change reviewed bytes."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'tools/covers/article-covers.mjs'
TITLE = 'Как начать работу с независимым подрядчиком и сохранить его самостоятельность'


@pytest.fixture
def cms():
    state = {'target': {'id': 1077, 'slug': 'contractor-onboarding', 'locale': 'ru',
                        'title': TITLE, 'cover': None}, 'calls': [], 'gets': 0,
             'switch_locale_at': None, 'upload_error': False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, payload, status=200):
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def do_GET(self):
            state['calls'].append(('GET', self.path, b''))
            state['gets'] += 1
            if state['gets'] == state['switch_locale_at']:
                state['target']['locale'] = 'en'
            self.reply({'data': state['target']})

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            state['calls'].append(('POST', self.path, body))
            if state['upload_error']:
                return self.reply({'error': 'server body must not leak secret=test-cover-token'}, 500)
            self.reply([{'id': 501, 'url': 'https://example.com/ru-cover.png'}])

        def do_PUT(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            state['calls'].append(('PUT', self.path, body))
            state['target']['cover'] = {'id': json.loads(body)['data']['cover']}
            self.reply({'data': state['target']})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state['url'] = f'http://127.0.0.1:{server.server_port}'
    yield state
    server.shutdown()
    thread.join()


def run(cms, *args):
    env = {**os.environ, 'STRAPI_URL': cms['url'], 'STRAPI_TOKEN': 'test-cover-token'}
    return subprocess.run(['node', str(CLI), *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=30)


def render(cms, tmp_path):
    result = run(cms, '--slug=contractor-onboarding', '--locale=ru', '--id=1077',
                 '--format=png', f'--out={tmp_path}')
    assert result.returncode == 0, result.stderr
    return tmp_path / 'contractor-onboarding.png'


def upload(cms, image, receipt):
    return run(cms, '--slug=contractor-onboarding', '--locale=ru', '--id=1077',
               f'--file={image}', f'--receipt={receipt}')


@pytest.mark.parametrize('args', [('--locale=ru',), ('--locale=ru', '--id=1077'),
                                 ('--slug=x', '--id=0'), ('--slug=x', '--id=1.5')])
def test_invalid_selection_fails_before_any_api_call(cms, args):
    assert run(cms, *args).returncode != 0
    assert cms['calls'] == []


@pytest.mark.parametrize('key,value', [('locale', 'en'), ('id', 1078), ('slug', 'other')])
def test_wrong_locale_id_or_slug_is_never_rendered_or_uploaded(cms, tmp_path, key, value):
    cms['target'][key] = value
    result = run(cms, '--slug=contractor-onboarding', '--locale=ru', '--id=1077',
                 f'--out={tmp_path}')
    assert result.returncode != 0
    assert not any(c[0] in ('POST', 'PUT') for c in cms['calls'])
    assert not list(tmp_path.iterdir())


def test_ru_render_is_read_only_complete_and_has_full_mobile_receipts(cms, tmp_path):
    image = render(cms, tmp_path)
    receipt = json.loads(Path(str(image) + '.render.json').read_text())
    assert receipt['target_id'] == 1077 and receipt['locale'] == 'ru'
    assert receipt['title'] == TITLE
    assert ' '.join(receipt['title_layout']['lines']) == TITLE
    assert receipt['full_title_preserved'] is True and receipt['glyph_coverage'] == 'PASS'
    assert receipt['file_sha256'] == hashlib.sha256(image.read_bytes()).hexdigest()
    assert struct.unpack('>II', image.read_bytes()[16:24]) == (1200, 800)
    preview = Path(receipt['preview_path'])
    assert struct.unpack('>II', preview.read_bytes()[16:24]) == (390, 260)
    assert all(c[0] == 'GET' for c in cms['calls'])
    assert parse_qs(urlparse(cms['calls'][0][1]).query)['locale'] == ['ru']


@pytest.mark.parametrize('title', ['Нет глифа 🛸', 'Оченьдлинноеслово' * 150,
                                  'Очень длинный заголовок ' * 250])
def test_unsupported_glyphs_or_unfittable_title_fail_without_truncation(cms, tmp_path, title):
    cms['target']['title'] = title
    result = run(cms, '--slug=contractor-onboarding', '--locale=ru', '--id=1077', f'--out={tmp_path}')
    assert result.returncode != 0
    assert not any(c[0] in ('POST', 'PUT') for c in cms['calls'])
    assert not list(tmp_path.iterdir())


def test_existing_reviewed_png_uploaded_exactly_and_retry_is_idempotent(cms, tmp_path):
    image = render(cms, tmp_path)
    receipt = tmp_path / 'cover-upload.json'
    result = upload(cms, image, receipt)
    assert result.returncode == 0, result.stderr
    saved = json.loads(receipt.read_text())
    assert saved['status'] == 'complete' and saved['media_id'] == 501
    assert saved['target_id'] == 1077 and saved['locale'] == 'ru'
    posts = [c for c in cms['calls'] if c[0] == 'POST']
    puts = [c for c in cms['calls'] if c[0] == 'PUT']
    assert len(posts) == len(puts) == 1
    assert image.read_bytes() in posts[0][2]
    assert puts[0][1] == '/api/articles/1077'
    assert json.loads(puts[0][2]) == {'data': {'cover': 501}}
    assert upload(cms, image, receipt).returncode == 0
    assert len([c for c in cms['calls'] if c[0] == 'POST']) == 1
    assert len([c for c in cms['calls'] if c[0] == 'PUT']) == 1


def test_modified_reviewed_bytes_cannot_be_uploaded(cms, tmp_path):
    image = render(cms, tmp_path)
    image.write_bytes(image.read_bytes() + b'changed')
    assert upload(cms, image, tmp_path / 'upload.json').returncode != 0
    assert not any(c[0] in ('POST', 'PUT') for c in cms['calls'])


def test_locale_changes_before_association_keep_media_id_and_never_touch_en(cms, tmp_path):
    image = render(cms, tmp_path)
    receipt = tmp_path / 'upload.json'
    cms['gets'] = 0
    cms['switch_locale_at'] = 3
    assert upload(cms, image, receipt).returncode != 0
    saved = json.loads(receipt.read_text())
    assert saved['status'] == 'uploaded' and saved['media_id'] == 501
    assert len([c for c in cms['calls'] if c[0] == 'POST']) == 1
    assert not any(c[0] == 'PUT' for c in cms['calls'])


def test_ambiguous_upload_is_not_reposted_and_error_body_is_not_printed(cms, tmp_path):
    image = render(cms, tmp_path)
    receipt = tmp_path / 'upload.json'
    cms['upload_error'] = True
    result = upload(cms, image, receipt)
    assert result.returncode != 0 and 'secret=' not in result.stderr + result.stdout
    assert json.loads(receipt.read_text())['status'] == 'upload_pending'
    assert upload(cms, image, receipt).returncode != 0
    assert len([c for c in cms['calls'] if c[0] == 'POST']) == 1


def test_default_english_selected_render_still_writes_webp(cms, tmp_path):
    cms['target'].update(locale='en', title='Contractor onboarding')
    result = run(cms, '--slug=contractor-onboarding', f'--out={tmp_path}')
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'contractor-onboarding.webp').read_bytes().startswith(b'RIFF')
    assert parse_qs(urlparse(cms['calls'][0][1]).query)['locale'] == ['en']
