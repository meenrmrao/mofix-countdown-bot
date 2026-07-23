"""
Entry point: run the MOFIX Telegram bot.
    python run_bot.py
"""
import asyncio

from bot.bot import main

if __name__ == "__main__":
    asyncio.run(main())
