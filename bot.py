import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import os

# ========== ТВОИ ДАННЫЕ ==========
BOT_TOKEN_USER = "8679586191:AAHib52i7jM3N5I6u3eWDCw8rXo_QdfMs7A"
BOT_TOKEN_ADMIN = "8204249394:AAFl0oEka_lucGgQggx2SK-f8_cxXWZ56gM"
ADMIN_IDS = [8523282279]
# =================================

# База данных
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        full_name TEXT,
        phone TEXT,
        card_number TEXT,
        bank_name TEXT,
        balance INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending'
    )
''')
conn.commit()

class UserStates(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    waiting_card = State()
    waiting_bank = State()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="💰 Поработать")], [KeyboardButton(text="💼 Баланс")], [KeyboardButton(text="👥 Привести друга")]],
    resize_keyboard=True
)

bank_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="ОТП", callback_data="bank_otp")],
    [InlineKeyboardButton(text="Совкомбанк", callback_data="bank_sovkom")],
    [InlineKeyboardButton(text="Т-Банк", callback_data="bank_tbank")],
    [InlineKeyboardButton(text="Озон", callback_data="bank_ozon")],
    [InlineKeyboardButton(text="Альфа", callback_data="bank_alfa")]
])

user_bot = Bot(token=BOT_TOKEN_USER)
user_dp = Dispatcher(storage=MemoryStorage())

@user_dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await message.answer("👋 Введите ваше ФИО:", reply_markup=main_keyboard)
    await state.set_state(UserStates.waiting_full_name)

@user_dp.message(UserStates.waiting_full_name)
async def get_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("📞 Введите номер телефона:")
    await state.set_state(UserStates.waiting_phone)

@user_dp.message(UserStates.waiting_phone)
async def get_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("💳 Введите номер карты:")
    await state.set_state(UserStates.waiting_card)

@user_dp.message(UserStates.waiting_card)
async def get_card(message: types.Message, state: FSMContext):
    await state.update_data(card=message.text)
    await message.answer("🏦 Введите название банка:")
    await state.set_state(UserStates.waiting_bank)

@user_dp.message(UserStates.waiting_bank)
async def get_bank(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute('INSERT OR REPLACE INTO users (telegram_id, full_name, phone, card_number, bank_name, status) VALUES (?, ?, ?, ?, ?, "active")',
                   (message.from_user.id, data['full_name'], data['phone'], data['card'], message.text))
    conn.commit()
    await message.answer("✅ Регистрация завершена!", reply_markup=main_keyboard)
    await state.clear()

@user_dp.message(F.text == "💰 Поработать")
async def work(message: types.Message):
    await message.answer("🏦 Выберите банк:", reply_markup=bank_keyboard)

@user_dp.callback_query(F.data.startswith("bank_"))
async def bank_chosen(callback: types.CallbackQuery):
    await callback.message.answer("✅ Функция загрузки выписки появится позже.")
    await callback.answer()

@user_dp.message(F.text == "💼 Баланс")
async def balance(message: types.Message):
    cursor.execute('SELECT balance FROM users WHERE telegram_id = ?', (message.from_user.id,))
    row = cursor.fetchone()
    bal = row[0] if row else 0
    await message.answer(f"💰 Баланс: {bal} ₽")

@user_dp.message(F.text == "👥 Привести друга")
async def refer(message: types.Message):
    await message.answer("👥 Ссылка: https://t.me/CroakExpbot?start=ref")

admin_bot = Bot(token=BOT_TOKEN_ADMIN)
admin_dp = Dispatcher(storage=MemoryStorage())

@admin_dp.message(Command("start"))
async def admin_start(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("👑 Админ-панель активна")

async def main():
    await user_bot.delete_webhook()
    await admin_bot.delete_webhook()
    asyncio.create_task(user_dp.start_polling(user_bot))
    asyncio.create_task(admin_dp.start_polling(admin_bot))
    print("✅ Боты запущены на Render!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())