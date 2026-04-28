import asyncio
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ========== ТОКЕНЫ И НАСТРОЙКИ ==========
GNOME_TOKEN = "8758482757:AAGkoDnYfopuQmMO3eqKdJ4-MBseANSUWWg"
ADMIN_TOKEN = "8204249394:AAFl0oEka_lucGgQggx2SK-f8_cxXWZ56gM"
MASTER_ID = 8523282279
# =======================================

# База данных
conn = sqlite3.connect('bot.db', check_same_thread=False)
cur = conn.cursor()
cur.executescript('''
    CREATE TABLE IF NOT EXISTS gnomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        full_name TEXT,
        phone TEXT,
        card_number TEXT,
        bank_name TEXT,
        balance INTEGER DEFAULT 0,
        ref_code TEXT,
        invited_by INTEGER,
        status TEXT DEFAULT 'pending',
        reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS work_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bank TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS withdrawal_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        card_number TEXT,
        status TEXT DEFAULT 'pending'
    );
    CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        date DATE
    );
''')
conn.commit()

# ========== FSM СОСТОЯНИЯ ==========
class GnomeReg(StatesGroup):
    full_name = State()
    phone = State()
    card_number = State()
    bank_name = State()

class AdminStates(StatesGroup):
    waiting_amount = State()
    waiting_user_id = State()

# ========== КЛАВИАТУРЫ ==========
gnome_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Баланс")],
        [KeyboardButton(text="👥 Реферальная ссылка")],
        [KeyboardButton(text="📝 Отчёт")],
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Заявки на работу")],
        [KeyboardButton(text="👥 Все гномы")],
        [KeyboardButton(text="💰 Начислить деньги")],
        [KeyboardButton(text="📊 Статистика")]
    ],
    resize_keyboard=True
)

# ========== ГНОМИЙ БОТ ==========
gnome_bot = Bot(token=GNOME_TOKEN)
gnome_dp = Dispatcher(storage=MemoryStorage())

def generate_ref_code(telegram_id):
    return f"ref_{telegram_id}_{datetime.now().strftime('%Y%m%d')}"

@gnome_dp.message(Command("start"))
async def gnome_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cur.execute('SELECT * FROM gnomes WHERE telegram_id = ?', (user_id,))
    user = cur.fetchone()
    
    # Проверка реферального кода
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1]
        cur.execute('SELECT id FROM gnomes WHERE ref_code = ?', (ref_code,))
        inviter = cur.fetchone()
        if inviter:
            await state.update_data(invited_by=inviter[0])
    
    if not user:
        await message.answer("📝 Добро пожаловать! Введите ваше ФИО:")
        await state.set_state(GnomeReg.full_name)
    else:
        await message.answer(f"👋 С возвращением, {user[2]}!", reply_markup=gnome_kb)

@gnome_dp.message(GnomeReg.full_name)
async def reg_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await message.answer("📞 Введите номер телефона:")
    await state.set_state(GnomeReg.phone)

@gnome_dp.message(GnomeReg.phone)
async def reg_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await message.answer("💳 Введите номер карты:")
    await state.set_state(GnomeReg.card_number)

@gnome_dp.message(GnomeReg.card_number)
async def reg_card(message: types.Message, state: FSMContext):
    await state.update_data(card_number=message.text)
    await message.answer("🏦 Введите название банка:")
    await state.set_state(GnomeReg.bank_name)

@gnome_dp.message(GnomeReg.bank_name)
async def reg_bank(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    ref_code = generate_ref_code(user_id)
    
    cur.execute('''
        INSERT INTO gnomes (telegram_id, full_name, phone, card_number, bank_name, ref_code, invited_by, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
    ''', (user_id, data['full_name'], data['phone'], data['card_number'], message.text, ref_code, data.get('invited_by')))
    conn.commit()
    
    # Начисление бонуса пригласившему
    if data.get('invited_by'):
        cur.execute('UPDATE gnomes SET balance = balance + 100 WHERE id = ?', (data['invited_by'],))
        conn.commit()
    
    await message.answer("✅ Регистрация завершена!", reply_markup=gnome_kb)
    await state.clear()

@gnome_dp.message(F.text == "💰 Баланс")
async def gnome_balance(message: types.Message):
    cur.execute('SELECT balance FROM gnomes WHERE telegram_id = ?', (message.from_user.id,))
    row = cur.fetchone()
    balance = row[0] if row else 0
    await message.answer(f"💰 Ваш баланс: {balance} ₽")

@gnome_dp.message(F.text == "👥 Реферальная ссылка")
async def gnome_ref(message: types.Message):
    cur.execute('SELECT ref_code FROM gnomes WHERE telegram_id = ?', (message.from_user.id,))
    row = cur.fetchone()
    if row:
        bot_username = (await gnome_bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={row[0]}"
        await message.answer(f"👥 Ваша реферальная ссылка:\n{link}")

@gnome_dp.message(F.text == "📝 Отчёт")
async def gnome_report(message: types.Message, state: FSMContext):
    await message.answer("📝 Введите сумму остатка на балансе (например: 1500):")
    await state.set_state("waiting_report_amount")

@gnome_dp.message(lambda m: m.text.isdigit(), lambda m: m.state == "waiting_report_amount")
async def gnome_report_amount(message: types.Message, state: FSMContext):
    amount = int(message.text)
    cur.execute('INSERT INTO daily_reports (user_id, amount, date) VALUES (?, ?, DATE("now"))',
                (message.from_user.id, amount))
    conn.commit()
    await message.answer(f"✅ Отчёт на {amount} ₽ отправлен!")
    await state.clear()

# ========== АДМИН-БОТ ==========
admin_bot = Bot(token=ADMIN_TOKEN)
admin_dp = Dispatcher(storage=MemoryStorage())

def is_master(user_id):
    return user_id == MASTER_ID

@admin_dp.message(Command("start"))
async def admin_start(message: types.Message):
    if not is_master(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    await message.answer("👑 Админ-панель", reply_markup=admin_kb)

@admin_dp.message(F.text == "📋 Заявки на работу")
async def admin_requests(message: types.Message):
    if not is_master(message.from_user.id): return
    cur.execute('SELECT id, user_id, bank FROM work_requests WHERE status = "pending"')
    requests = cur.fetchall()
    if not requests:
        await message.answer("📭 Нет новых заявок")
        return
    for req in requests:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{req[0]}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{req[0]}")]
        ])
        await message.answer(f"📝 Заявка #{req[0]}\nПользователь: {req[1]}\nБанк: {req[2]}", reply_markup=kb)

@admin_dp.callback_query(F.data.startswith("approve_"))
async def approve_request(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    cur.execute('UPDATE work_requests SET status = "approved" WHERE id = ?', (req_id,))
    conn.commit()
    await callback.message.edit_text("✅ Заявка одобрена")
    await callback.answer()

@admin_dp.callback_query(F.data.startswith("reject_"))
async def reject_request(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    cur.execute('UPDATE work_requests SET status = "rejected" WHERE id = ?', (req_id,))
    conn.commit()
    await callback.message.edit_text("❌ Заявка отклонена")
    await callback.answer()

@admin_dp.message(F.text == "👥 Все гномы")
async def admin_gnomes(message: types.Message):
    if not is_master(message.from_user.id): return
    cur.execute('SELECT id, full_name, phone, balance FROM gnomes WHERE status = "active"')
    gnomes = cur.fetchall()
    if not gnomes:
        await message.answer("📭 Нет гномов")
        return
    text = "🧑‍🌾 Список гномов:\n\n"
    for g in gnomes:
        text += f"├ ID: {g[0]} | {g[1]} | {g[2]} | баланс: {g[3]} ₽\n"
    await message.answer(text)

@admin_dp.message(F.text == "💰 Начислить деньги")
async def admin_pay_start(message: types.Message, state: FSMContext):
    if not is_master(message.from_user.id): return
    await message.answer("💰 Введите ID гнома и сумму через пробел:\nПример: 123 500")
    await state.set_state("waiting_pay_data")

@admin_dp.message(AdminStates.waiting_amount)
async def admin_pay_process(message: types.Message, state: FSMContext):
    try:
        user_id, amount = map(int, message.text.split())
        cur.execute('UPDATE gnomes SET balance = balance + ? WHERE telegram_id = ?', (amount, user_id))
        conn.commit()
        await message.answer(f"✅ Начислено {amount} ₽ гному {user_id}")
    except:
        await message.answer("❌ Неверный формат. Введите: ID_гнома сумма")
    await state.clear()

@admin_dp.message(F.text == "📊 Статистика")
async def admin_stats(message: types.Message):
    if not is_master(message.from_user.id): return
    cur.execute('SELECT COUNT(*) FROM gnomes')
    total_users = cur.fetchone()[0]
    cur.execute('SELECT SUM(balance) FROM gnomes')
    total_balance = cur.fetchone()[0] or 0
    await message.answer(f"📊 Статистика:\n├ Гномов: {total_users}\n└ Общий баланс: {total_balance} ₽")

# ========== ЗАПУСК ==========
async def main():
    await asyncio.gather(
        gnome_dp.start_polling(gnome_bot),
        admin_dp.start_polling(admin_bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
