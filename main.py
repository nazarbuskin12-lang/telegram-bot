import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

GNOME_TOKEN = "8758482757:AAGkoDnYfopuQmMO3eqKdJ4-MBseANSUWWg"
ADMIN_TOKEN = "8204249394:AAFl0oEka_lucGgQggx2SK-f8_cxXWZ56gM"
MASTER_ID = 8523282279

bot1 = Bot(token=GNOME_TOKEN)
bot2 = Bot(token=ADMIN_TOKEN)

dp1 = Dispatcher()
dp2 = Dispatcher()

@dp1.message(Command("start"))
async def g_start(m: types.Message):
    await m.answer("✅ Гномий бот работает!")

@dp2.message(Command("start"))
async def a_start(m: types.Message):
    if m.from_user.id == MASTER_ID:
        await m.answer("✅ Админ-бот работает!")

async def main():
    await asyncio.gather(
        dp1.start_polling(bot1),
        dp2.start_polling(bot2)
    )
    print("✅ Два бота запущены")

if __name__ == "__main__":
    asyncio.run(main())
