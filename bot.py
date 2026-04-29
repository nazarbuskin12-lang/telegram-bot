import asyncio
import sqlite3
import random
import requests
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
ADMIN_LOGIN = "AdminCroakEx"
ADMIN_PASSWORD = "Administration12"
REFERRAL_BONUS = 500

# ========== НАСТРОЙКИ СМС ==========
SMS_API_URL = "https://smsc.ru/sys/send.php"
SMS_LOGIN = "+79132349837"
SMS_PASSWORD = "Nazarbuskin1234@"

IMAGES = {
    "welcome": "https://cdn-icons-png.flaticon.com/512/906/906196.png",
    "balance": "https://cdn-icons-png.flaticon.com/512/2331/2331969.png",
    "referral": "https://cdn-icons-png.flaticon.com/512/2333/2333030.png",
    "report": "https://cdn-icons-png.flaticon.com/512/2333/2333211.png",
    "work": "https://cdn-icons-png.flaticon.com/512/2331/2331985.png",
    "withdraw": "https://cdn-icons-png.flaticon.com/512/2333/2333036.png",
    "deal": "https://cdn-icons-png.flaticon.com/512/2331/2331970.png",
    "success": "https://cdn-icons-png.flaticon.com/512/2333/2333243.png",
    "code": "https://cdn-icons-png.flaticon.com/512/2333/2333033.png"
}

conn = sqlite3.connect('bot.db', check_same_thread=False)
cur = conn.cursor()
cur.executescript('''
    CREATE TABLE IF NOT EXISTS gnomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        full_name TEXT,
        phone TEXT,
        bank_name TEXT,
        balance INTEGER DEFAULT 0,
        ref_code TEXT,
        invited_by INTEGER,
        verified INTEGER DEFAULT 0,
        work_status TEXT DEFAULT 'pending',
        status TEXT DEFAULT 'active',
        reg_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS work_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        bank TEXT,
        phone TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS deals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        gnome_id INTEGER,
        deal_text TEXT,
        status TEXT DEFAULT 'waiting_payment',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS withdrawal_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        phone TEXT,
        bank_name TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS admins (
        telegram_id INTEGER PRIMARY KEY,
        is_verified INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS sms_codes (
        phone TEXT PRIMARY KEY,
        code TEXT,
        expires_at TIMESTAMP
    );
''')
conn.commit()

async def send_with_image(bot, chat_id, text, image_key, keyboard=None):
    img_url = IMAGES.get(image_key, IMAGES["welcome"])
    await bot.send_photo(chat_id, photo=img_url, caption=text, reply_markup=keyboard)

class GnomeReg(StatesGroup):
    full_name = State()
    phone = State()
    bank_name = State()
    waiting_code = State()

class WithdrawStates(StatesGroup):
    waiting_amount = State()
    waiting_phone = State()
    waiting_bank = State()

class WorkRequestStates(StatesGroup):
    waiting_bank = State()
    waiting_phone = State()

class AdminStates(StatesGroup):
    waiting_amount = State()
    waiting_requisites = State()
    waiting_deal_text = State()
    waiting_gnome_selection = State()

class DealStates(StatesGroup):
    waiting_amount = State()
    waiting_balance = State()

class AdminAuth(StatesGroup):
    waiting_login = State()
    waiting_password = State()

gnome_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="👥 Реферальная ссылка")],
        [KeyboardButton(text="📝 Отчёт"), KeyboardButton(text="💼 Заработать")],
        [KeyboardButton(text="💸 Вывод средств")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Заявки на работу")],
        [KeyboardButton(text="👥 Все гномы")],
        [KeyboardButton(text="💰 Начислить деньги")],
        [KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="💸 Заявки на вывод")],
        [KeyboardButton(text="🤝 Взаимодействовать")]
    ],
    resize_keyboard=True
)

interact_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📤 Отправить реквизиты")],
        [KeyboardButton(text="💰 Отправить сделку")]
    ],
    resize_keyboard=True
)

gnome_deal_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Пришли деньги")],
        [KeyboardButton(text="❌ Не приходят")]
    ],
    resize_keyboard=True
)

gnome_bot = Bot(token=GNOME_TOKEN)
gnome_dp = Dispatcher(storage=MemoryStorage())
admin_bot = Bot(token=ADMIN_TOKEN)
admin_dp = Dispatcher(storage=MemoryStorage())

def generate_ref_code(telegram_id):
    return f"ref_{telegram_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

def is_verified(user_id):
    cur.execute('SELECT verified FROM gnomes WHERE telegram_id = ?', (user_id,))
    row = cur.fetchone()
    return row and row[0] == 1

def is_working(user_id):
    cur.execute('SELECT work_status FROM gnomes WHERE telegram_id = ?', (user_id,))
    row = cur.fetchone()
    return row and row[0] == 'working'

def get_gnome_name(user_id):
    cur.execute('SELECT full_name FROM gnomes WHERE telegram_id = ?', (user_id,))
    row = cur.fetchone()
    return row[0] if row else "Гном"

def get_gnome_balance(user_id):
    cur.execute('SELECT balance FROM gnomes WHERE telegram_id = ?', (user_id,))
    row = cur.fetchone()
    return row[0] if row else 0

def update_balance(user_id, amount):
    cur.execute('UPDATE gnomes SET balance = balance + ? WHERE telegram_id = ?', (amount, user_id))
    conn.commit()

def reduce_balance(user_id, amount):
    cur.execute('UPDATE gnomes SET balance = balance - ? WHERE telegram_id = ?', (amount, user_id))
    conn.commit()

def set_work_status(user_id, status):
    cur.execute('UPDATE gnomes SET work_status = ? WHERE telegram_id = ?', (status, user_id))
    conn.commit()

def generate_sms_code(phone):
    code = str(random.randint(100000, 999999))
    cur.execute('INSERT OR REPLACE INTO sms_codes (phone, code, expires_at) VALUES (?, ?, datetime("now", "+10 minutes"))', (phone, code))
    conn.commit()
    return code

def send_sms(phone, code):
    try:
        response = requests.get(SMS_API_URL, params={
            'login': SMS_LOGIN,
            'psw': SMS_PASSWORD,
            'phones': phone,
            'mes': f"Ваш код подтверждения: {code}",
            'fmt': 3
        }, timeout=10)
        return response.status_code == 200
    except:
        return False

def verify_sms_code(phone, code):
    cur.execute('SELECT code FROM sms_codes WHERE phone = ? AND expires_at > datetime("now")', (phone,))
    row = cur.fetchone()
    return row and row[0] == code

def get_working_gnomes():
    cur.execute('SELECT telegram_id, full_name FROM gnomes WHERE work_status = "working" AND status = "active"')
    return cur.fetchall()

# ========== ГНОМИЙ БОТ (упрощённо для демо) ==========
@gnome_dp.message(Command("start"))
async def gnome_start(message: types.Message, state: FSMContext):
    await send_with_image(gnome_bot, message.from_user.id,
        "🌟 **Бот работает!**\n\nВся логика сохранена.", "welcome", gnome_kb)

@gnome_dp.message(F.text == "💰 Баланс")
async def gnome_balance(message: types.Message):
    await send_with_image(gnome_bot, message.from_user.id,
        f"💰 Баланс: {get_gnome_balance(message.from_user.id)} ₽", "balance")

@gnome_dp.message(F.text == "👥 Реферальная ссылка")
async def gnome_ref(message: types.Message):
    await send_with_image(gnome_bot, message.from_user.id,
        "👥 Ваша ссылка скоро будет", "referral")

@gnome_dp.message(F.text == "📝 Отчёт")
async def gnome_report(message: types.Message):
    await send_with_image(gnome_bot, message.from_user.id,
        "📝 Отправьте сумму остатка", "report")

@gnome_dp.message(F.text == "💼 Заработать")
async def gnome_work(message: types.Message):
    await send_with_image(gnome_bot, message.from_user.id,
        "🏦 Выберите банк в разработке", "work")

@gnome_dp.message(F.text == "💸 Вывод средств")
async def gnome_withdraw(message: types.Message):
    await send_with_image(gnome_bot, message.from_user.id,
        "💸 Вывод в разработке", "withdraw")

# ========== АДМИН-БОТ (упрощённо) ==========
@admin_dp.message(Command("start"))
async def admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id == MASTER_ID:
        await message.answer("👑 Админ-панель", reply_markup=admin_kb)
    else:
        await message.answer("🔐 Введите логин:")
        await state.set_state(AdminAuth.waiting_login)

@admin_dp.message(AdminAuth.waiting_login)
async def admin_login(message: types.Message, state: FSMContext):
    if message.text == ADMIN_LOGIN:
        await state.update_data(login=message.text)
        await message.answer("🔐 Введите пароль:")
        await state.set_state(AdminAuth.waiting_password)
    else:
        await message.answer("❌ Неверный логин")

@admin_dp.message(AdminAuth.waiting_password)
async def admin_password(message: types.Message, state: FSMContext):
    if message.text == ADMIN_PASSWORD:
        await message.answer("✅ Вход выполнен!", reply_markup=admin_kb)
        await state.clear()
    else:
        await message.answer("❌ Неверный пароль")

async def main():
    print("✅ Боты запущены на Render")
    await asyncio.gather(
        gnome_dp.start_polling(gnome_bot),
        admin_dp.start_polling(admin_bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
