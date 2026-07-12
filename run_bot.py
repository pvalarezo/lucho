#!/usr/bin/env python3
"""Run the Lucho Telegram bot in polling mode (no webhook, no SSL, no public IP).

Requirements:
1. Create a bot with @BotFather on Telegram
2. Copy the token to .env: TELEGRAM_BOT_TOKEN=your_token_here
3. Run: python run_bot.py
"""

import asyncio
from app.bot import main

if __name__ == "__main__":
    asyncio.run(main())
