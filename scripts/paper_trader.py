"""Monthly momentum-rotation paper trader for Alpaca's paper account (stdlib only).

Strategy (pre-registered 2026-11-12, do not tune): each month, score 11 ETFs by the average
of their 1/3/6/12-month total returns. Hold the top 3 at 1/3 each. Any pick that scores
below SHY (cash) is replaced by SHY. Rebalance on the first trading day of each month,
using prior month-end closes.

Every run appends account equity and the SPY benchmark to journal/equity.csv. Rebalance
runs also write journal/trades.csv.

Env: ALPACA_KEY_ID, ALPACA_SECRET_KEY (PAPER keys only). DRY_RUN=1 computes the targets
without placing orders. The script refuses to run against any non-paper endpoint.
"""
import csv, datetime as dt, json, os, sys, urllib.parse, urllib.request

TRADE = 'https://paper-api.alpaca.markets'
DATA = 'https://data.alpaca.markets'
UNIV = ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'VNQ', 'TLT', 'IEF', 'GLD', 'DBC', 'LQD']
CASH, TOP, LBS = 'SHY', 3, (1, 3, 6, 12)
JOURNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'journal')
assert 'paper' in TRADE, 'paper trading only'

H = {'APCA-API-KEY-ID': os.environ.get('ALPACA_KEY_ID', ''),
     'APCA-API-SECRET-KEY': os.environ.get('ALPACA_SECRET_KEY', '')}


def api(base, path, params=None, body=None, method=None):
    url = base + path + ('?' + urllib.parse.urlencode(params) if params else '')
    req = urllib.request.Request(url, headers={**H, 'Content-Type': 'application/json'},
                                 data=json.dumps(body).encode() if body else None,
                                 method=method or ('POST' if body else 'GET'))
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read()
        return json.loads(txt) if txt else None


def month_end_closes(today):
    """Adjusted closes at each month-end, from daily IEX bars (free feed)."""
    start = (today - dt.timedelta(days=430)).isoformat()
    bars, token = {}, None
    while True:
        p = {'symbols': ','.join(UNIV + [CASH]), 'timeframe': '1Day', 'start': start,
             'adjustment': 'all', 'feed': 'iex', 'limit': 10000}
        if token:
            p['page_token'] = token
        j = api(DATA, '/v2/stocks/bars', p)
        for s, bs in j['bars'].items():
            bars.setdefault(s, []).extend(bs)
        token = j.get('next_page_token')
        if not token:
            break
    me = {}
    this_month = today.strftime('%Y-%m')
    for s, bs in bars.items():
        last = {}
        for b in bs:
            m = b['t'][:7]
            if m < this_month:  # completed months only
                last[m] = b['c']
        me[s] = [last[m] for m in sorted(last)]
    return me


def targets(me):
    def score(s):
        x = me[s]
        return sum(x[-1] / x[-1 - l] - 1 for l in LBS) / len(LBS)
    sc = {s: score(s) for s in UNIV if len(me.get(s, [])) > max(LBS)}
    cash = score(CASH)
    w = {}
    for s in sorted(sc, key=sc.get, reverse=True)[:TOP]:
        k = s if sc[s] > cash else CASH
        w[k] = w.get(k, 0) + 1 / TOP
    return w, sc, cash


def append(name, row, header):
    os.makedirs(JOURNAL, exist_ok=True)
    f = os.path.join(JOURNAL, name)
    new = not os.path.exists(f)
    with open(f, 'a', newline='') as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(header)
        w.writerow(row)


def main():
    if not H['APCA-API-KEY-ID']:
        sys.exit('Missing ALPACA_KEY_ID / ALPACA_SECRET_KEY')
    dry = os.environ.get('DRY_RUN') == '1'
    force = os.environ.get('FORCE_REBALANCE') == '1'
    today = dt.date.today()
    clock = api(TRADE, '/v2/clock')
    cal = api(TRADE, '/v2/calendar', {'start': today.replace(day=1).isoformat(), 'end': today.isoformat()})
    first_day = bool(cal) and cal[0]['date'] == today.isoformat()
    acct = api(TRADE, '/v2/account')
    equity = float(acct['equity'])
    spy = api(DATA, '/v2/stocks/SPY/trades/latest', {'feed': 'iex'})['trade']['p']
    append('equity.csv', [today.isoformat(), round(equity, 2), spy], ['date', 'equity', 'spy_price'])
    print(f'{today} equity={equity:.2f} SPY={spy} market_open={clock["is_open"]} first_trading_day={first_day}')

    if not (first_day or force or dry):
        return
    me = month_end_closes(today)
    w, sc, cash = targets(me)
    print('scores:', {k: round(v, 4) for k, v in sorted(sc.items(), key=lambda kv: -kv[1])}, 'cash:', round(cash, 4))
    print('targets:', w)
    if dry:
        return
    if not clock['is_open']:
        sys.exit('Market closed; not trading.')
    pos = {p['symbol']: float(p['market_value']) for p in api(TRADE, '/v2/positions')}
    goal = {s: equity * 0.99 * wt for s, wt in w.items()}  # keep 1% buffer
    orders = []
    for s in set(pos) | set(goal):
        diff = goal.get(s, 0) - pos.get(s, 0)
        if s not in goal and s in pos:
            orders.append((s, 'sell', None))  # close fully
        elif abs(diff) >= max(25, 0.01 * equity):
            orders.append((s, 'buy' if diff > 0 else 'sell', round(abs(diff), 2)))
    # sells first to free cash
    for s, side, notional in sorted(orders, key=lambda o: o[1] != 'sell'):
        if notional is None:
            api(TRADE, f'/v2/positions/{s}', method='DELETE')
        else:
            api(TRADE, '/v2/orders', body={'symbol': s, 'side': side, 'type': 'market',
                                            'time_in_force': 'day', 'notional': str(notional)})
        append('trades.csv', [today.isoformat(), s, side, notional or 'close', json.dumps(w)],
               ['date', 'symbol', 'side', 'notional', 'targets'])
        print('order', s, side, notional or 'close')


if __name__ == '__main__':
    main()
