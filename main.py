import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

GNOME_TOKEN = "8679586191:AAHib52i7jM3N5I6u3eWDCw8rXo_QdfMs7A"
ADMIN_TOKEN = "8204249394:AAFl0oEka_lucGgQggx2SK-f8_cxXWZ56gM"
SUPPORT_TOKEN = "8164113755:AAHwgQlUSrlREOK5uizy9jk4bADewAZljhg"
MASTER_ID = 8523282279

bot1 = Bot(token=GNOME_TOKEN)
bot2 = Bot(token=ADMIN_TOKEN)
bot3 = Bot(token=SUPPORT_TOKEN)

dp1 = Dispatcher()
dp2 = Dispatcher()
dp3 = Dispatcher()

@dp1.message(Command("start"))
async def g_start(m: types.Message):
    await m.answer("✅ Гномий бот работает!")

@dp2.message(Command("start"))
async def a_start(m: types.Message):
    if m.from_user.id == MASTER_ID:
        await m.answer("✅ Админ-бот работает!")

@dp3.message(Command("start"))
async def s_start(m: types.Message):
    await m.answer("✅ Техподдержка работает!")

async def main():
    await asyncio.gather(
        dp1.start_polling(bot1),
        dp2.start_polling(bot2),
        dp3.start_polling(bot3)
    )
    print("✅ Три бота запущены")

if __name__ == "__main__":
    asyncio.run(main())
