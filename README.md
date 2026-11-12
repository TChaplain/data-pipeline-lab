# Paper trader setup (about 10 minutes, all free)

Claude can't create accounts or handle API keys, so these steps are yours. Everything after this is automated.

1. **Alpaca paper account.** Sign up at https://alpaca.markets. A paper-only account needs no funding and no ID check. In the dashboard, make sure the top-left switch says **Paper**, then go to *API Keys → Generate New Keys*. Keep the two values on screen.
2. **New GitHub repo.** At https://github.com/new, name it `paper-trader`, set it to **Private**, tick "Add a README", and create it. Then tell Claude it exists. Claude will push this folder to it.
3. **Add the keys as secrets.** In the repo, go to *Settings → Secrets and variables → Actions → New repository secret*. Add `ALPACA_KEY_ID` and `ALPACA_SECRET_KEY` with the values from step 1.
4. Claude then runs one dry run from the Actions tab. After that the bot runs every weekday. It trades only on the first trading day of each month and commits the journal back to the repo.

Cost is $0. Private repos get 2,000 free Actions minutes a month, and this uses about 25.

## Memecoin paper lab
`scripts/memecoin_lab.py` runs every 10 minutes with no keys or wallet. It paper-buys $1 of Solana tokens under 8 pre-registered rules (including the news system: Telegram calls and trending lists; add public channel names to `config/tg_channels.txt`) and tracks every one until it's sold or rugs. Run `python scripts/scoreboard.py` to see win rate, rug rate, best multiple and P&L by strategy.
