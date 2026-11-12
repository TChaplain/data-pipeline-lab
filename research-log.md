# Research log

Every idea we test goes here before testing, with the result afterwards, including the failures.

| Date | Idea & source | Why it should work | Held-out 2016–2026 result (10 bps) | Verdict |
|---|---|---|---|---|
| 2026-11-12 | SPY 10-month SMA timing (Faber 2007) | Trend persistence; investors underreact, then herd | 8.1%/yr, max drawdown -25% vs SPY 14.7%, -24% | Rejected: lower return, no drawdown benefit this decade |
| 2026-11-12 | Faber GTAA-5 (Faber 2007) | Trend filter across 5 asset classes | 5.9%/yr, max drawdown -9% | Rejected on return; best drawdown control |
| 2026-11-12 | Dual momentum GEM (Antonacci 2014) | Relative and absolute momentum | 7.6%/yr, max drawdown -26% | Rejected |
| 2026-11-12 | Top-3 momentum rotation, 11 ETFs, 1/3/6/12-month average score | Cross-asset momentum plus a cash filter | 10.0%/yr, Sharpe 0.89, max drawdown -16% vs SPY 0.99, -24% | **Paper-trading.** Passes the drawdown bar and the Sharpe bar (≥ 0.89). At 30 bps: 8.4%/yr, Sharpe 0.77, which fails the cost bar. Watch costs closely. |
| 2026-11-12 | 10-month SMA on S&P 500, 1871–2023 (Shiller data) | Same as above, much longer history | 9.1% vs 9.2%/yr; max drawdown -47% vs -82% | Confirms trend rules mainly cut crashes. Note: Shiller prices are monthly averages, which flatters the rule a little. |
| 2026-11-12 | Memecoin paper lab: 4 pre-registered rules on new Solana pools (ape everything, early momentum, graduates, 10x moonshot hold) | Tests whether a fast outsider can catch the rare 100x tokens before snipers and insiders dump | Forward paper test, started when the repo goes live. Costs 5% in and 5% out; a pool under $500 liquidity counts as a rug | Running |
| 2026-11-12 | Lab rule `dex_boosted`: tokens someone just paid to promote on DexScreener | A paid promotion shows a team with budget and an attention push | Forward paper test | Running |
| 2026-11-12 | Lab rule `smart_follow`, our own smart-money tracker: record the first 10 buyer wallets of new pools; a wallet that was early in a 5x pool counts as "smart"; buy when 2+ smart wallets are early in a new pool | Some wallets show persistent skill (arXiv 2601.08641: smart wallets about +14%/trade, copiers about +3% after frictions) | Forward paper test | Running |
| 2026-11-12 | News lab: post-earnings drift. Paper-buy $1,000 of a US stock over $10 after a headline reports an earnings beat or raised guidance (Alpaca/Benzinga free feed), hold 20 trading days, score against SPY | Investors underreact to earnings surprises (post-earnings-announcement drift, Bernard and Thomas 1989; weaker since publication) | Forward paper test, 10 bps costs | Running |
