# BCN Half-Marathon Bib Tracker

Checks the official RPM Sports marketplace for newly available 2027 Barcelona half-marathon bibs and sends a Telegram notification.

## Local check

```bash
python3 tracker.py --dry-run
```

The checker uses the marketplace's server-rendered availability table and does not attempt to log in, solve CAPTCHA challenges, or purchase a bib.

## GitHub Actions setup

1. Create a Telegram bot with [@BotFather](https://t.me/BotFather) and copy its token.
2. Send the bot a message, then obtain your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. In the repository, add these Actions secrets under **Settings → Secrets and variables → Actions**:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. Run **Check bib marketplace** manually once from the Actions tab.

The scheduled check runs daily at 06:00 UTC. GitHub may start scheduled workflows a few minutes late. The workflow commits only the current listing IDs to `state.json`, so an unchanged listing does not repeatedly notify you.
