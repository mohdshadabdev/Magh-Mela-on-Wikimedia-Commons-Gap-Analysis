"""Small, polite client for the Wikimedia Commons Action API.

- One request at a time, with a pause between requests.
- Sends maxlag and a descriptive User-Agent (no email address).
- Retries on HTTP 429 / 5xx and on maxlag errors, honouring Retry-After.
- Handles API continuation for list and prop queries.
"""
import json
import time

import requests

API = 'https://commons.wikimedia.org/w/api.php'
USER_AGENT = ('MaghMelaCommonsAnalysis/1.0 '
              '(https://commons.wikimedia.org/wiki/User:Sanskardubeydev)')
PAUSE = 1.0          # seconds between requests
MAX_RETRIES = 8

_session = requests.Session()
_session.headers['User-Agent'] = USER_AGENT
_last_call = 0.0
request_count = 0


def call(params):
    """One API request. Returns parsed JSON."""
    global _last_call, request_count
    params = dict(params, format='json', formatversion='2', maxlag='5')
    delay = 2
    for attempt in range(MAX_RETRIES):
        wait = PAUSE - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()
        try:
            r = _session.get(API, params=params, timeout=60)
        except requests.RequestException as e:
            print(f'  network error ({e}); retrying in {delay}s')
            time.sleep(delay)
            delay = min(delay * 2, 120)
            continue
        request_count += 1
        if r.status_code == 429 or r.status_code >= 500:
            retry_after = int(r.headers.get('Retry-After', delay))
            print(f'  HTTP {r.status_code}; waiting {retry_after}s')
            time.sleep(retry_after)
            delay = min(delay * 2, 120)
            continue
        r.raise_for_status()
        data = r.json()
        err = data.get('error')
        if err and err.get('code') == 'maxlag':
            retry_after = int(r.headers.get('Retry-After', 5))
            print(f'  maxlag; waiting {retry_after}s')
            time.sleep(retry_after)
            continue
        if err:
            raise RuntimeError(f"API error {err.get('code')}: {err.get('info')}")
        return data
    raise RuntimeError(f'Gave up after {MAX_RETRIES} attempts: {params}')


def query_all(params):
    """Yield every 'query' block of a query, following 'continue'."""
    params = dict(params, action='query')
    cont = {}
    while True:
        data = call({**params, **cont})
        if 'query' in data:
            yield data['query']
        if 'continue' not in data:
            break
        cont = data['continue']


def save_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
