import asyncio
import logging

import aiocron
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import handlers
from handlers import bot, router


async def main():
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)

    aiocron.crontab('*/30 * * * *', handlers.update_state)
    aiocron.crontab('0 0 * * *', handlers.send_best_win_percent)
    aiocron.crontab('0 12 * * *', handlers.send_message_links)

    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
