"""Memecoin paper lab. It measures, with fake money, what a fast outsider actually earns
buying brand-new Solana tokens in $1 bets. It uses free public data (GeckoTerminal) and needs no keys or wallet.

Each run (every 10 minutes from GitHub Actions):
  1. Pull the newest Solana pools.
  2. Each pre-registered strategy below decides whether to "buy" $1 of paper at the
     observed price, plus a realistic cost penalty for late entry, fees and slippage.
  3. Re-price every open position and apply its exit rules. A pool whose liquidity
     disappears counts as a rug and closes at $0.
  4. Closed trades go to journal/meme_trades.csv; open state lives in journal/meme_state.json.

Rules were pre-registered on 2026-11-12. Do not tune them after seeing results; add a new
strategy with a new name instead.
"""
import csv, datetime as dt, json, os, time, urllib.request

API = 'https://api.geckoterminal.com/api/v2'
J = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'journal')
STATE, TRADES = os.path.join(J, 'meme_state.json'), os.path.join(J, 'meme_trades.csv')
SIZE = 1.0            # paper dollars per entry: matches a real $10 bankroll split into ~8 bets
ENTRY_COST = 0.05     # 5%: ~1% platform fee + slippage + being minutes behind the snipers
EXIT_COST = 0.05
FIXED_USD = 0.03      # priority + network fees per side (token-account rent is refundable, so not counted)
RUG_LIQ = 500         # pool liquidity below $500 means you can't get out: value 0
MAX_OPEN = 150        # per strategy

STRATS = {
    # name: (entry filter(pool) -> bool, exit params)
    'ape_everything': (lambda p: p['liq'] >= 2_000,
                       dict(tp=None, sl=None, trail=None, max_h=24)),
    'early_momentum': (lambda p: p['age_m'] <= 60 and p['vol_h1'] >= 50_000 and p['buys_h1'] > 1.3 * p['sells_h1'] and p['liq'] >= 10_000,
                       dict(tp=None, sl=-0.5, trail=0.5, max_h=48)),
    'graduates': (lambda p: p['dex'] in ('pumpswap', 'raydium', 'raydium-clmm', 'meteora') and p['liq'] >= 20_000,
                  dict(tp=None, sl=-0.5, trail=0.4, max_h=72)),
    'moonshot_hold': (lambda p: p['age_m'] <= 30 and p['liq'] >= 5_000 and p['buys_h1'] >= 100,
                      dict(tp=10.0, sl=None, trail=None, max_h=168)),  # sell everything at 10x or after 7 days
    # Added 2026-11-12. "Someone paid DexScreener to promote it" signal:
    'dex_boosted': (lambda p: p.get('boosted') and p['liq'] >= 10_000,
                    dict(tp=None, sl=-0.5, trail=0.5, max_h=48)),
    # Added 2026-11-12. Our own smart-money tracker: 2+ early buyers who were early in a 5x+ pool before.
    'smart_follow': (lambda p: p.get('smart_n', 0) >= 2 and p['liq'] >= 5_000,
                     dict(tp=None, sl=-0.5, trail=0.5, max_h=48)),
}
WALLETS = os.path.join(J, 'smart_wallets.json')   # wallet -> {'wins': n, 'seen': n}
TRACK = os.path.join(J, 'tracked_pools.json')     # pool -> {'ref': price, 'peak': x, 'buyers': [...], 't': iso}
DS = 'https://api.dexscreener.com'
EARLY_N = 10          # first N distinct buyer wallets per pool
TRACK_PER_RUN = 8     # pools whose early trades we record each run (rate limit: 30 calls/min)
WIN_X = 5.0           # a pool counts as a win for its early buyers at 5x from first sight


def get(path, base=API):
    time.sleep(2.1)  # stay under GeckoTerminal's 30 calls/min
    for attempt in range(4):
        try:
            req = urllib.request.Request(base + path, headers={'Accept': 'application/json', 'User-Agent': 'paper-lab'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # rate limit (30/min) or transient error
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f'failed {path}')


def parse(d, now):
    a = d['attributes']
    tx = (a.get('transactions') or {}).get('h1') or {}
    created = dt.datetime.fromisoformat(a['pool_created_at'].replace('Z', '+00:00')) if a.get('pool_created_at') else now
    return {'addr': a['address'], 'name': a['name'], 'dex': d['relationships']['dex']['data']['id'],
            'price': float(a['base_token_price_usd'] or 0), 'liq': float(a['reserve_in_usd'] or 0),
            'vol_h1': float((a.get('volume_usd') or {}).get('h1') or 0),
            'buys_h1': tx.get('buys', 0) or 0, 'sells_h1': tx.get('sells', 0) or 0,
            'age_m': (now - created).total_seconds() / 60}


def parse_ds(d, now):
    tx = (d.get('txns') or {}).get('h1') or {}
    created = d.get('pairCreatedAt') or now.timestamp() * 1000
    return {'addr': d['pairAddress'], 'name': (d.get('baseToken') or {}).get('symbol', '?'), 'dex': d.get('dexId', ''),
            'price': float(d.get('priceUsd') or 0), 'liq': float((d.get('liquidity') or {}).get('usd') or 0),
            'vol_h1': float((d.get('volume') or {}).get('h1') or 0), 'buys_h1': tx.get('buys', 0), 'sells_h1': tx.get('sells', 0),
            'age_m': (now.timestamp() * 1000 - created) / 60000, 'boosted': True}


def early_buyers(addr):
    tr = get(f'/networks/solana/pools/{addr}/trades')['data']
    buys = sorted((t['attributes'] for t in tr if t['attributes']['kind'] == 'buy'), key=lambda a: a['block_number'])
    out = []
    for a in buys:
        w = a['tx_from_address']
        if w not in out:
            out.append(w)
        if len(out) >= EARLY_N:
            break
    return out


def close(pos, mult, reason, now, rows):
    value = SIZE * mult * (1 - EXIT_COST) - FIXED_USD if mult > 0 else 0.0
    rows.append([now.isoformat(timespec='minutes'), pos['strat'], pos['name'], pos['addr'], pos['opened'],
                 round(mult, 3), round(value - SIZE - FIXED_USD, 3), reason])


def main():
    now = dt.datetime.now(dt.timezone.utc)
    os.makedirs(J, exist_ok=True)
    st = json.load(open(STATE)) if os.path.exists(STATE) else {'open': [], 'seen': {}}
    new = []
    for page in (1, 2, 3):
        new += [parse(d, now) for d in get(f'/networks/solana/new_pools?page={page}')['data']]
    # 0. boosted tokens from DexScreener and our own smart-wallet signal
    try:
        boosts = [b['tokenAddress'] for b in get('/token-boosts/latest/v1', DS) if b.get('chainId') == 'solana'][:30]
        if boosts:
            pairs = get('/tokens/v1/solana/' + ','.join(boosts), DS)
            best = {}
            for d in pairs:
                t = d['baseToken']['address']
                if t not in best or (d.get('liquidity') or {}).get('usd', 0) > (best[t].get('liquidity') or {}).get('usd', 0):
                    best[t] = d
            new += [parse_ds(d, now) for d in best.values()]
    except Exception as e:
        print('dexscreener skipped:', e)
    wallets = json.load(open(WALLETS)) if os.path.exists(WALLETS) else {}
    track = json.load(open(TRACK)) if os.path.exists(TRACK) else {}
    fresh = [p for p in new if not p.get('boosted') and p['addr'] not in track and p['liq'] >= 5_000 and p['price'] > 0]
    for p in sorted(fresh, key=lambda p: -p['buys_h1'])[:TRACK_PER_RUN]:
        try:
            buyers = early_buyers(p['addr'])
        except Exception:
            continue
        track[p['addr']] = {'ref': p['price'], 'peak': 1.0, 'buyers': buyers, 't': now.isoformat(), 'won': False}
        for w in buyers:
            wallets.setdefault(w, {'wins': 0, 'seen': 0})['seen'] += 1
        p['smart_n'] = sum(1 for w in buyers if wallets[w]['wins'] >= 1)
    # 1. entries
    opened = 0
    for p in new:
        if p['price'] <= 0:
            continue
        for name, (entry, _) in STRATS.items():
            key = f'{name}:{p["addr"]}'
            if key in st['seen'] or sum(o['strat'] == name for o in st['open']) >= MAX_OPEN:
                continue
            try:
                ok = entry(p)
            except Exception:
                ok = False
            if ok:
                st['seen'][key] = now.isoformat()
                st['open'].append({'strat': name, 'addr': p['addr'], 'name': p['name'],
                                   'entry': None,  # set from GeckoTerminal's pool price below, so entry and exit use one price source 'peak': 1.0, 'half_sold': False,
                                   'opened': now.isoformat(timespec='minutes')})
                opened += 1
    # 2. re-price open positions, 30 pools per request
    addrs = sorted({o['addr'] for o in st['open']} | set(track))
    live = {}
    for i in range(0, len(addrs), 30):
        for d in get('/networks/solana/pools/multi/' + ','.join(addrs[i:i + 30]))['data']:
            q = parse(d, now)
            live[q['addr']] = q
    # credit early buyers of pools that hit WIN_X; forget pools after 48h
    for a, tp in list(track.items()):
        q = live.get(a)
        if q and tp['ref'] > 0:
            tp['peak'] = max(tp['peak'], q['price'] / tp['ref'])
            if tp['peak'] >= WIN_X and not tp['won']:
                tp['won'] = True
                for w in tp['buyers']:
                    wallets.setdefault(w, {'wins': 0, 'seen': 0})['wins'] += 1
        if (now - dt.datetime.fromisoformat(tp['t'])).total_seconds() > 48 * 3600:
            del track[a]
    json.dump(track, open(TRACK, 'w'))
    live_buyers = {w for tp in track.values() for w in tp['buyers']}
    json.dump({w: v for w, v in wallets.items() if v['wins'] or w in live_buyers}, open(WALLETS, 'w'))
    rows, still = [], []
    for o in st['open']:
        q = live.get(o['addr'])
        params = STRATS[o['strat']][1]
        age_h = (now - dt.datetime.fromisoformat(o['opened'])).total_seconds() / 3600
        if o['entry'] is None:  # just opened this run
            if q and q['liq'] >= RUG_LIQ and q['price'] > 0:
                o['entry'] = q['price'] * (1 + ENTRY_COST)
                still.append(o)
            continue  # untradeable at entry: never counted as a trade
        if q is None or q['liq'] < RUG_LIQ:
            close(o, 0, 'rug/no liquidity', now, rows); continue
        mult = q['price'] / o['entry']
        o['peak'] = max(o['peak'], mult)
        if params['tp'] and mult >= params['tp']:
            close(o, mult, f'take profit {params["tp"]}x', now, rows)
        elif params['sl'] is not None and mult <= 1 + params['sl']:
            close(o, mult, 'stop loss', now, rows)
        elif params['trail'] and o['peak'] >= 2 and mult <= o['peak'] * (1 - params['trail']):
            close(o, mult, 'trailing stop', now, rows)
        elif age_h >= params['max_h']:
            close(o, mult, 'time exit', now, rows)
        else:
            still.append(o)
    st['open'] = still
    # keep 'seen' small: forget entries older than 8 days
    cutoff = (now - dt.timedelta(days=8)).isoformat()
    st['seen'] = {k: v for k, v in st['seen'].items() if v > cutoff}
    json.dump(st, open(STATE, 'w'))
    if rows:
        new_file = not os.path.exists(TRADES)
        with open(TRADES, 'a', newline='') as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(['closed', 'strategy', 'token', 'pool', 'opened', 'multiple', 'pnl_usd', 'reason'])
            w.writerows(rows)
    print(f'{now:%F %H:%M} new_pools={len(new)} opened={opened} closed={len(rows)} open={len(still)}')


if __name__ == '__main__':
    main()
