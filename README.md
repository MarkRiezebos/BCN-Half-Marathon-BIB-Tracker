# BCN Half-Marathon Bib Tracker

Checks the official RPM Sports marketplace for newly available 2027 Barcelona half-marathon bibs and sends a Telegram notification.

## Local check

```bash
python3 tracker.py --dry-run
```

The checker uses the marketplace's server-rendered availability table and does not attempt to log in, solve CAPTCHA challenges, or purchase a bib.
It fails visibly if the expected marketplace table or its headers disappear, rather than treating a changed page as an empty marketplace.
It also sends a Telegram warning when that structural check fails, so the parser can be updated if RPM changes the page.

## GitHub Actions setup

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Send the bot a message, then obtain your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. In the repository, add these Actions secrets under **Settings → Secrets and variables → Actions**:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Run **Check bib marketplace** manually once from the Actions tab.

The scheduled check runs every 15 minutes, around the clock, at `:07`, `:22`, `:37`, and `:52` in the `Europe/Madrid` timezone. The minutes are offset from the start of the hour to reduce GitHub scheduling congestion. GitHub may still start scheduled workflows a few minutes late. The workflow commits only the current listing IDs to `state.json`, so an unchanged listing does not repeatedly notify you.
