"""Monthly backtester for rules-based ETF strategies.

Signal at month-end t uses only prices up to t. The new weights earn month t+1's return.
Costs: COST per unit of turnover, charged on both buys and sells.
Usage: python3 backtest.py [cost_bps]
"""
import sys
import numpy as np
import pandas as pd

HERE = __file__.rsplit('/', 1)[0]
COST = (float(sys.argv[1]) if len(sys.argv) > 1 else 10) / 10000  # 10 bps per side by default
CASH = 'SHY'

px = pd.read_csv(f'{HERE}/data/monthly_adjclose.csv', index_col=0)
ret = px.pct_change()


# ---------------- strategies: f(px_upto_t) -> dict(weights) ----------------
def buy_hold(sym):
    return lambda p: {sym: 1.0}


def sixty_forty(p):
    return {'SPY': 0.6, 'IEF': 0.4}


def sma_timing(sym, n=10):
    def f(p):
        s = p[sym].dropna()
        return {sym: 1.0} if s.iloc[-1] > s.iloc[-n:].mean() else {CASH: 1.0}
    return f


def gtaa5(p, n=10):
    """Faber (2007) 'A Quantitative Approach to Tactical Asset Allocation'."""
    w = {}
    for a in ['SPY', 'EFA', 'IEF', 'VNQ', 'DBC']:
        s = p[a].dropna()
        k = a if s.iloc[-1] > s.iloc[-n:].mean() else CASH
        w[k] = w.get(k, 0) + 0.2
    return w


def gem(p, eq=('SPY', 'EFA'), bond='AGG', lb=12):
    """Antonacci Global Equities Momentum (dual momentum)."""
    r = {a: p[a].iloc[-1] / p[a].iloc[-1 - lb] - 1 for a in eq + (CASH,)}
    best = max(eq, key=lambda a: r[a])
    return {best: 1.0} if r[best] > r[CASH] else {bond: 1.0}


UNIV = ['SPY', 'QQQ', 'IWM', 'EFA', 'EEM', 'VNQ', 'TLT', 'IEF', 'GLD', 'DBC', 'LQD']


def rel_mom(p, top=3, lbs=(1, 3, 6, 12)):
    """Rotate into the top-N assets by average 1/3/6/12-month return, each also
    required to beat cash (absolute momentum). Keller/Butler/Faber-style."""
    sc = {}
    for a in UNIV:
        s = p[a].dropna()
        if len(s) <= max(lbs):
            continue
        sc[a] = np.mean([s.iloc[-1] / s.iloc[-1 - l] - 1 for l in lbs])
    c = p[CASH].dropna()
    cash_sc = np.mean([c.iloc[-1] / c.iloc[-1 - l] - 1 for l in lbs])
    picks = sorted(sc, key=sc.get, reverse=True)[:top]
    w = {}
    for a in picks:
        k = a if sc[a] > cash_sc else CASH
        w[k] = w.get(k, 0) + 1 / top
    return w


STRATS = {
    'Buy & hold SPY': (buy_hold('SPY'), ['SPY']),
    '60/40 SPY/IEF': (sixty_forty, ['SPY', 'IEF']),
    'SPY 10-mo SMA timing': (sma_timing('SPY'), ['SPY', CASH]),
    'Faber GTAA-5': (gtaa5, ['SPY', 'EFA', 'IEF', 'VNQ', 'DBC', CASH]),
    'Dual momentum (GEM)': (gem, ['SPY', 'EFA', 'AGG', CASH]),
    'Top-3 momentum rotation': (rel_mom, UNIV + [CASH]),
}


def run(f, need, warm=13):
    start = max(px[a].first_valid_index() for a in need)
    dates = list(px.loc[start:].index)
    out, prev = [], {}
    for i in range(warm, len(dates) - 1):
        t, t1 = dates[i], dates[i + 1]
        w = f(px.loc[:t])
        turn = sum(abs(w.get(k, 0) - prev.get(k, 0)) for k in set(w) | set(prev))
        r = sum(wt * ret.at[t1, k] for k, wt in w.items()) - turn * COST
        out.append((t1, r, turn, max(w, key=w.get)))
        # drift weights with returns
        tot = sum(wt * (1 + ret.at[t1, k]) for k, wt in w.items())
        prev = {k: wt * (1 + ret.at[t1, k]) / tot for k, wt in w.items()}
    return pd.DataFrame(out, columns=['month', 'ret', 'turnover', 'top']).set_index('month')


def stats(r):
    r = r.dropna()
    if len(r) < 12:
        return {}
    eq = (1 + r).cumprod()
    yrs = len(r) / 12
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(12)
    dd = (eq / eq.cummax() - 1).min()
    return {'CAGR %': round(cagr * 100, 1), 'Vol %': round(vol * 100, 1),
            'Sharpe*': round(r.mean() / r.std() * np.sqrt(12), 2),
            'MaxDD %': round(dd * 100, 1), 'Months': len(r)}


if __name__ == '__main__':
    res = {k: run(f, need) for k, (f, need) in STRATS.items()}
    common = max(r.index[0] for r in res.values())
    periods = {
        f'Full common period ({common} to {px.index[-1]})': (common, px.index[-1]),
        'In-sample 2007-03 to 2015-12': ('2007-03', '2015-12'),
        'Out-of-sample 2016-01 to 2026-10 (untouched)': ('2016-01', '2026-10'),
        'Last 3 years 2023-11 to 2026-10': ('2023-11', '2026-10'),
    }
    print(f'Cost assumption: {COST*1e4:.0f} bps per side of turnover. Sharpe* = excess over 0, not cash.\n')
    for name, (a, b) in periods.items():
        print('==', name)
        rows = {k: stats(r.loc[a:b, 'ret']) for k, r in res.items()}
        print(pd.DataFrame(rows).T.to_string(), '\n')
    print('Avg annual turnover:', {k: round(r.turnover.mean() * 12, 1) for k, r in res.items()})
    for k, r in res.items():
        r.to_csv(f'{HERE}/results/{k.replace(" ", "_").replace("/", "-")}.csv')
