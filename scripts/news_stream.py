"""Fast news lab: reacts to Alpaca's live news stream within seconds (paper only, no orders).

Pre-registered 2026-11-12, do not tune. When a headline reports an earnings beat or raised
guidance (same classifier as news_lab.py) for a US stock above $10:
  - 'fast_5m'   paper-buys at the first price after the headline and sells 5 minutes later
  - 'fast_30m'  same entry, sells after 30 minutes
  - 'fast_eod'  same entry, sells when this shift ends (about end of day)
Each trade is scored against SPY over the same window, with 10 bps cost per side. Results go to
journal/news_fast_trades.csv. The question: does being seconds-fast to news beat the market
after costs, or is it already priced in by the time a free feed delivers it?

Runs in shifts from GitHub Actions (each job is capped at 6 hours). Env: ALPACA_KEY_ID, ALPACA_SECRET_KEY.
"""
import asyncio, csv, datetime as dt, json, os, sys, time, urllib.parse, urllib.request
import websockets
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from news_lab import EARN, BEAT, MISS, SKIP

KEY, SECRET = os.environ.get('ALPACA_KEY_ID', ''), os.environ.get('ALPACA_SECRET_KEY', '')
H = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}
J = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'journal')
OUT = os.path.join(J, 'news_fast_trades.csv')
COST = 0.001
SHIFT_END = time.time() + float(os.environ.get('SHIFT_MINUTES', '345')) * 60
HOLDS = {'fast_5m': 300, 'fast_30m': 1800}


def price(sym):
    url = 'https://data.alpaca.markets/v2/stocks/trades/latest?' + urllib.parse.urlencode({'symbols': sym + ',SPY', 'feed': 'iex'})
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=10) as r:
        t = json.load(r).get('trades', {})
    return (t.get(sym) or {}).get('p'), (t.get('SPY') or {}).get('p')


def record(rule, sym, t0, p0, s0, headline, lag):
    p1, s1 = price(sym)
    if not (p1 and s1):
        return
    r = p1 * (1 - COST) / (p0 * (1 + COST)) - 1
    rs = s1 / s0 - 1
    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['opened', 'rule', 'symbol', 'news_lag_s', 'return_%', 'spy_%', 'excess_%', 'headline'])
        w.writerow([t0, rule, sym, round(lag, 1), round(r * 100, 3), round(rs * 100, 3), round((r - rs) * 100, 3), headline[:200]])
    print(rule, sym, f'{r*100:+.2f}% vs SPY {rs*100:+.2f}%', flush=True)


async def trade(sym, headline, created):
    p0, s0 = price(sym)
    if not p0 or p0 < 10 or not s0:
        return
    t0 = dt.datetime.now(dt.timezone.utc)
    lag = (t0 - dt.datetime.fromisoformat(created.replace('Z', '+00:00'))).total_seconds()
    print('enter', sym, p0, f'lag={lag:.1f}s', '|', headline[:100], flush=True)
    done = 0
    for rule, secs in sorted(HOLDS.items(), key=lambda kv: kv[1]):
        wait = min(secs - done, SHIFT_END - time.time() - 60)
        if wait <= 0:
            break
        await asyncio.sleep(wait)
        done = secs
        record(rule, sym, t0.isoformat(timespec='seconds'), p0, s0, headline, lag)
    await asyncio.sleep(max(0, SHIFT_END - time.time() - 30))
    record('fast_eod', sym, t0.isoformat(timespec='seconds'), p0, s0, headline, lag)


async def main():
    if not KEY:
        sys.exit('Missing Alpaca keys')
    os.makedirs(J, exist_ok=True)
    seen, tasks, auth = set(), [], []
    while time.time() < SHIFT_END - 120:
        try:
            async with websockets.connect('wss://stream.data.alpaca.markets/v1beta1/news') as ws:
                await ws.send(json.dumps({'action': 'auth', 'key': KEY, 'secret': SECRET}))
                await ws.send(json.dumps({'action': 'subscribe', 'news': ['*']}))
                while time.time() < SHIFT_END - 120:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    except asyncio.TimeoutError:
                        continue
                    for m in json.loads(raw):
                        if m.get('T') != 'n' or m.get('id') in seen:
                            if m.get('T') in ('error', 'success', 'subscription'):
                                print('stream', m, flush=True)
                            continue
                        seen.add(m['id'])
                        h, syms = m.get('headline', ''), m.get('symbols', [])
                        if EARN.search(h) and BEAT.search(h) and not MISS.search(h) and not SKIP.search(h) and 1 <= len(syms) <= 2:
                            for s in syms:
                                if s.isalpha() and len(s) <= 5:
                                    tasks.append(asyncio.create_task(trade(s, h, m['created_at'])))
        except Exception as e:
            print('reconnect after error:', e, flush=True)
            await asyncio.sleep(5)
    await asyncio.gather(*tasks, return_exceptions=True)
    print('shift over; headlines:', len(seen), 'signals:', len(tasks), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
