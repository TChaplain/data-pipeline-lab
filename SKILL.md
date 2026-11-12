---
name: paper-trader
description: Research, backtest and paper-trade ETF strategies and run the memecoin paper lab, with honest out-of-sample testing and a gated $10 go-live plan. Use when TJ asks about trading, memecoins, or the paper accounts.
---

# Paper trader

This skill is a disciplined loop for finding out whether a trading idea really works. It uses paper money only. Never place real-money orders, and never enter or handle API keys: TJ stores the keys as GitHub secrets.

## Files
The code lives in the project folder `/mnt/project-files/trading/skill/paper-trader/` and in TJ's private GitHub repo `paper-trader`.
- `scripts/paper_trader.py` is the live strategy. It runs every weekday from GitHub Actions, logs equity, and rebalances on the first trading day of each month.
- `journal/equity.csv` and `journal/trades.csv` hold the scoreboard, committed by the bot.
- `backtest.py` and `longhistory.py` are the backtesters. `data/` holds monthly adjusted closes for 16 ETFs and Shiller's S&P 500 data since 1871.
- `research-log.md` lists every idea ever tested, including the failures.
- `scripts/memecoin_lab.py` paper-buys $1 of new Solana tokens every 30 minutes under 6 pre-registered rules, using the free GeckoTerminal and DexScreener APIs. `scripts/scoreboard.py` summarizes it. Its state lives in `journal/meme_state.json` and `journal/meme_trades.csv`. Our own smart-wallet list lives in `journal/smart_wallets.json` and `journal/tracked_pools.json`.

## What the evidence says (start here, don't re-derive it)
1. Most active traders lose. Large studies of day traders (Taiwan, Brazil) find that fewer than about 1% make a living from it after costs.
2. Published anomalies earn about 26% less out of sample and about 58% less after publication (McLean and Pontiff). A strategy from a book or video is the starting hypothesis, not the proof.
3. The edges with a century or more of evidence are trend-following and momentum (Hurst, Ooi and Pedersen; Moskowitz et al.). They mostly **cut big drawdowns**; they rarely beat a rising stock market on raw return.
4. Our own test (2026-11-12): from 2016 to 2026, no rotation strategy beat buy-and-hold SPY on return (14.7%/yr). The top-3 momentum rotation made 10.0%/yr with a -16% worst drawdown, versus SPY's -24%. Over 150 years, a 10-month moving-average rule matched the S&P 500 (9.1% vs 9.2%/yr) and cut the worst drawdown from -82% to -47%.

## The loop for any new idea
1. **Write it down first** in `research-log.md`: the exact rules, the source, why it should work (risk premium, behavioral bias, or structural reason), and how it could fail. If there's no reason it should work, don't test it.
2. **Rules must be mechanical**: no discretion, and no parameters chosen after seeing results. Use the source's default parameters.
3. **Backtest with costs** (10 and 30 bps per side) on data up to 2015 only.
4. **One shot at the held-out data** (2016 onward). Report it whatever it shows. Re-tuning after looking at held-out data turns it into in-sample data, so log the attempt as a failure instead.
5. **Pass bar**: on held-out data, Sharpe at least SPY's minus 0.1, *and* a worst drawdown at least 25% smaller than SPY's, *and* the result survives 30 bps costs. Otherwise it's rejected.
6. **Paper-trade** a passing idea for at least 6 months, alongside the current live strategy.
7. **Monthly review**: compare paper equity to SPY and 60/40, and check that live trades match what the backtest would have done the same month. A mismatch is a bug to fix.

## Hard rules
- Paper only. Real money is TJ's decision alone, and only after 12+ months of paper results that match the backtest.
- No leverage, options or shorting. Crypto and memecoins only through the memecoin lab below.
- Never present backtest returns as expected returns. Always show SPY alongside.
- Don't sell signals or advice to others: that needs investment-adviser registration.
- Transcripts of videos and books are input for step 1, never proof.

## Memecoin lab and the $10 go-live gate
- **Why outsiders usually lose:** snipers buy in the creation block using private feeds and paid priority; bundlers hold most of the supply from hidden wallets; insiders and paid influencers buy before the announcement; sandwich bots front-run orders. Never build or join bundling, insider buying, wash volume or paid pumps: that's fraud or market manipulation. The only legal edge is being a fast outsider who picks better.
- **The 6 rules:** ape_everything (the baseline that shows the cost of no edge), early_momentum, graduates, moonshot_hold (sell at 10x or after 7 days), dex_boosted (just paid for DexScreener promotion), and smart_follow (2+ early buyers that were early in a 5x pool before).
- **Where the evidence points:** smart_follow is the only rule with published support. Wallet skill persists: smart wallets make about +14% per trade, but copiers net about +3% after frictions (arXiv 2601.08641). Influencer wallets often sell into their followers, and the first influencer buy typically happens at about a $4.6k market cap with a second influencer within 9 seconds, so a slow copy is exit liquidity. Treat any rule that beats ape_everything by less than its costs as no edge.
- **Rejected for now:** the X API is pay-per-use, about $0.005 per post read (roughly $23/mo for 50 accounts), which breaks the $0 rule until there's income. A free option to add later is public Telegram call channels (t.me/s/<name>).
- **Costs modeled per side:** 5% (platform fee, slippage and lateness) plus $0.03 in fees. Token-account rent (about 0.00204 SOL) is refundable. A pool under $500 liquidity counts as a rug at $0.
- **Go-live gate:** one rule must show 300+ closed paper trades with positive total P&L after costs. Then, and only if TJ decides: put about $10 of SOL in a brand-new Phantom wallet, keep about $1.50 for fees, and place about 8 bets of $1. Never top up. Run the bundle and rug checks before each buy (mint and freeze authority revoked, top 10 holders under 30%). Follow exits exactly and close empty token accounts.
- **Roles:** Claude gives the exact token, amount and exit. TJ presses buy and sell, because Claude never places real-money crypto trades. Never ask for, accept or store a seed phrase or private key.
- Every swap is a US taxable event, so log every trade.
