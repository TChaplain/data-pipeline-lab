"""Summarize the memecoin paper lab: win rate, best hit, total P&L, and share of rugs, per strategy."""
import csv, os, collections
f = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'journal', 'meme_trades.csv')
by = collections.defaultdict(list)
for r in csv.DictReader(open(f)):
    by[r['strategy']].append(r)
print(f'{"strategy":16} {"trades":>6} {"win%":>6} {"rug%":>6} {"best x":>8} {"10x+":>5} {"P&L $":>9} {"per bet":>8}')
for s, rs in by.items():
    m = [float(r['multiple']) for r in rs]
    pnl = sum(float(r['pnl_usd']) for r in rs)
    print(f'{s:16} {len(rs):6} {100*sum(x>1.1 for x in m)/len(m):6.1f} {100*sum(r["reason"].startswith("rug") for r in rs)/len(rs):6.1f} '
          f'{max(m):8.1f} {sum(x>=10 for x in m):5} {pnl:9.2f} {pnl/len(rs):8.2f}')
