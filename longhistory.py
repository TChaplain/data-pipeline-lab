"""150-year test of the 10-month moving-average rule on the S&P 500 (Shiller data).
Total return includes dividends. Cash earns 0% (conservative; ignores T-bill interest)."""
import numpy as np, pandas as pd
d = pd.read_csv(__file__.rsplit('/',1)[0] + '/data/shiller_sp500_monthly.csv', parse_dates=['Date']).set_index('Date')
d = d[d.Dividend > 0]  # recent months lack dividend data
p = d.SP500
tr = p.pct_change() + (d.Dividend / 12) / p.shift(1)
sig = (p > p.rolling(10).mean()).shift(1)  # decided at prior month-end
COST = 0.001
trade = sig.astype(float).diff().abs().fillna(0)
strat = np.where(sig == True, tr, 0.0) - trade * COST
df = pd.DataFrame({'Buy & hold': tr, '10-mo SMA': strat}).dropna().iloc[10:]
def s(r):
    eq = (1 + r).cumprod(); y = len(r) / 12
    return pd.Series({'CAGR %': (eq.iloc[-1] ** (1 / y) - 1) * 100, 'MaxDD %': (eq / eq.cummax() - 1).min() * 100, 'Vol %': r.std() * 12 ** .5 * 100}).round(1)
print('Period', df.index[0].date(), 'to', df.index[-1].date())
print(pd.DataFrame({k: s(df[k]) for k in df}).T, '\n')
print('Per-decade CAGR % (buy&hold vs SMA):')
for dec, g in df.groupby(df.index.year // 10 * 10):
    if len(g) >= 60:
        print(dec, s(g['Buy & hold'])['CAGR %'], s(g['10-mo SMA'])['CAGR %'], ' maxDD', s(g['Buy & hold'])['MaxDD %'], s(g['10-mo SMA'])['MaxDD %'])
