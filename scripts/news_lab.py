"""News lab: tests the post-earnings drift idea using Alpaca's free news feed (Benzinga).

Rule (pre-registered 2026-11-12, do not tune): when a headline reports an earnings beat
(the keywords below) for a US stock trading above $10, paper-buy $1,000 at the latest
price on the next run, hold 20 trading days (about 28 calendar days), then sell. Each trade
is scored against SPY over the same days. Nothing is ordered at Alpaca: the ledger lives in
journal/news_trades.csv, so the ETF paper account stays clean. Every headline seen goes
to journal/news_log.csv for later research.

Env: ALPACA_KEY_ID, ALPACA_SECRET_KEY (data endpoints only).
"""
import csv, datetime as dt, json, os, re, sys, urllib.parse, urllib.request

DATA = 'https://data.alpaca.markets'
J = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'journal')
STATE, LOG, TRADES = (os.path.join(J, f) for f in ('news_state.json', 'news_log.csv', 'news_trades.csv'))
H = {'APCA-API-KEY-ID': os.environ.get('ALPACA_KEY_ID', ''), 'APCA-API-SECRET-KEY': os.environ.get('ALPACA_SECRET_KEY', '')}
BEAT = re.compile(r'\bbeats?\b.*\b(estimates?|expectations|consensus)\b|\b(tops|exceeds?|surpass(es)?|above)\b.*\b(estimates?|expectations|consensus)\b|\braises?\b.*\bguidance\b', re.I)
SKIP = re.compile(r'\bahead of\b|\bpreview\b|\bforecasters?\b|\banalysts? (revamp|adjust)', re.I)  # previews, not results
MISS = re.compile(r'\b(miss(es)?|below|lowers?|cuts?)\b.*\b(estimates?|expectations|consensus|guidance)\b', re.I)
EARN = re.compile(r'\b(EPS|earnings|Q[1-4]|quarter|revenue|sales)\b', re.I)
SIZE, HOLD_DAYS, COST = 1000.0, 28, 0.001  # 10 bps per side


def api(path, params):
    req = urllib.request.Request(DATA + path + '?' + urllib.parse.urlencode(params), headers=H)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def prices(symbols):
    out = {}
    syms = sorted(set(symbols))
    for i in range(0, len(syms), 100):
        j = api('/v2/stocks/trades/latest', {'symbols': ','.join(syms[i:i + 100]), 'feed': 'iex'})
        out.update({s: t['p'] for s, t in j.get('trades', {}).items()})
    return out


def main():
    if not H['APCA-API-KEY-ID']:
        sys.exit('Missing Alpaca keys')
    now = dt.datetime.now(dt.timezone.utc)
    os.makedirs(J, exist_ok=True)
    st = json.load(open(STATE)) if os.path.exists(STATE) else {'since': (now - dt.timedelta(days=1)).isoformat(), 'open': [], 'seen': []}
    # 1. pull new headlines
    news, token = [], None
    while True:
        p = {'start': st['since'][:19] + 'Z', 'limit': 50, 'sort': 'asc', 'include_content': 'false'}
        if token:
            p['page_token'] = token
        j = api('/v1beta1/news', p)
        news += j.get('news', [])
        token = j.get('next_page_token')
        if not token or len(news) > 2000:
            break
    candidates = {}
    new_log = not os.path.exists(LOG)
    with open(LOG, 'a', newline='') as f:
        w = csv.writer(f)
        if new_log:
            w.writerow(['time', 'symbols', 'headline', 'signal'])
        for n in news:
            if n['id'] in st['seen']:
                continue
            st['seen'].append(n['id'])
            h = n['headline']
            sig = 'beat' if EARN.search(h) and BEAT.search(h) and not MISS.search(h) and not SKIP.search(h) else ('miss' if EARN.search(h) and MISS.search(h) else '')
            w.writerow([n['created_at'], ' '.join(n['symbols']), h, sig])
            if sig == 'beat' and 1 <= len(n['symbols']) <= 2:
                for s in n['symbols']:
                    if s.isalpha() and len(s) <= 5:
                        candidates.setdefault(s, h)
    st['seen'] = st['seen'][-5000:]
    st['since'] = now.isoformat()
    # 2. price everything we need
    held = {o['sym'] for o in st['open']}
    px = prices(list(candidates) + list(held) + ['SPY'])
    spy = px.get('SPY')
    # 3. entries
    for s, h in candidates.items():
        if s in held or s not in px or px[s] < 10 or not spy:
            continue
        st['open'].append({'sym': s, 'entry': px[s] * (1 + COST), 'spy0': spy, 'opened': now.isoformat(), 'headline': h[:200]})
        print('enter', s, px[s], '|', h[:120])
    # 4. exits after HOLD_DAYS
    rows, still = [], []
    for o in st['open']:
        age = (now - dt.datetime.fromisoformat(o['opened'])).days
        if age >= HOLD_DAYS and o['sym'] in px and spy:
            r = px[o['sym']] * (1 - COST) / o['entry'] - 1
            rs = spy / o['spy0'] - 1
            rows.append([now.date().isoformat(), o['sym'], o['opened'][:10], round(r * 100, 2), round(rs * 100, 2),
                         round((r - rs) * 100, 2), round(SIZE * r, 2), o['headline']])
        else:
            still.append(o)
    st['open'] = still
    json.dump(st, open(STATE, 'w'))
    if rows:
        new_t = not os.path.exists(TRADES)
        with open(TRADES, 'a', newline='') as f:
            w = csv.writer(f)
            if new_t:
                w.writerow(['closed', 'symbol', 'opened', 'return_%', 'spy_%', 'excess_%', 'pnl_usd', 'headline'])
            w.writerows(rows)
    print(f'{now:%F %H:%M} headlines={len(news)} beats={len(candidates)} open={len(still)} closed={len(rows)}')


if __name__ == '__main__':
    main()
