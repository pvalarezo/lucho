#!/usr/bin/env python3
"""Set up Telegram webhook for production use.

Usage:
    python scripts/setup_telegram_webhook.py [--url URL] [--delete] [--info]

Examples:
    # Set webhook (uses default lucho-dev.apx5.com)
    python scripts/setup_telegram_webhook.py

    # Set webhook with custom URL
    python scripts/setup_telegram_webhook.py --url https://example.com/telegram/webhook

    # Get current webhook info
    python scripts/setup_telegram_webhook.py --info

    # Delete webhook (return to polling mode)
    python scripts/setup_telegram_webhook.py --delete
"""

import argparse
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.telegram import set_webhook, get_webhook_info, delete_webhook
from app.config import settings

DEFAULT_URL = "https://lucho-dev.apx5.com/telegram/webhook"


async def main():
    parser = argparse.ArgumentParser(description="Manage Telegram bot webhook")
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Webhook URL (default: {DEFAULT_URL})",
    )
    parser.add_argument("--delete", action="store_true", help="Delete the webhook")
    parser.add_argument("--info", action="store_true", help="Get current webhook info")
    parser.add_argument(
        "--keep-pending",
        action="store_true",
        help="Don't drop pending updates when setting webhook",
    )
    args = parser.parse_args()

    if not settings.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is not set in .env")
        sys.exit(1)

    if args.info:
        print("📡 Getting webhook info...")
        info = await get_webhook_info()
        if info and info.get("ok"):
            result = info["result"]
            print(f"   URL: {result.get('url', 'NOT SET')}")
            print(f"   Has custom certificate: {result.get('has_custom_certificate', False)}")
            print(f"   Pending updates: {result.get('pending_update_count', 0)}")
            print(f"   Max connections: {result.get('max_connections', 'default')}")
            if result.get("last_error_date"):
                print(f"   Last error: {result.get('last_error_message', 'unknown')}")
            print(f"   Full response: {result}")
        else:
            print(f"   Failed: {info}")
        return

    if args.delete:
        print("🗑️  Deleting webhook...")
        result = await delete_webhook(drop_pending_updates=not args.keep_pending)
        if result and result.get("ok"):
            print("✅ Webhook deleted successfully.")
        else:
            print(f"❌ Failed: {result}")
        return

    # Set webhook
    print(f"🔗 Setting webhook to: {args.url}")
    print(f"   Drop pending updates: {not args.keep_pending}")
    result = await set_webhook(args.url, drop_pending_updates=not args.keep_pending)
    if result and result.get("ok"):
        print("✅ Webhook set successfully!")
    else:
        print(f"❌ Failed: {result}")


if __name__ == "__main__":
    asyncio.run(main())
