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

# ========== НАСТРОЙКИ СМС (smsc.ru) ==========
SMS_API_URL = "https://smsc.ru/sys/send.php"
SMS_LOGIN = "+79132349837"
SMS_PASSWORD = "Nazarbuskin1234@"

# ========== КАРТИНКИ ==========
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
# ============================================

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

# ========== ГНОМИЙ БОТ ==========
@gnome_dp.message(Command("start"))
async def gnome_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    cur.execute('SELECT * FROM gnomes WHERE telegram_id = ?', (user_id,))
    user = cur.fetchone()
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        ref_code = args[1]
        cur.execute('SELECT id, telegram_id FROM gnomes WHERE ref_code = ?', (ref_code,))
        inviter = cur.fetchone()
        if inviter and inviter[1] != user_id:
            await state.update_data(invited_by=inviter[0])
    
    if not user:
        await send_with_image(gnome_bot, user_id, 
            "🌟 **Добро пожаловать в бота «Гном»!**\n\n"
            "💰 Зарабатывай, выполняя задания.\n"
            "👥 Приводи друзей и получай бонусы.\n\n"
            "📝 Введите ваше ФИО:", "welcome")
        await state.set_state(GnomeReg.full_name)
    elif is_verified(user_id):
        name = get_gnome_name(user_id)
        await send_with_image(gnome_bot, user_id,
            f"👋 **С возвращением, {name}!**\n\n"
            f"💰 Баланс: {get_gnome_balance(user_id)} ₽\n\n"
            f"📌 Используйте кнопки меню.", "balance", gnome_kb)
    else:
        await send_with_image(gnome_bot, user_id,
            f"⏳ Привет, {user[2]}! Верификация не пройдена.", "code")

@gnome_dp.message(GnomeReg.full_name)
async def reg_full_name(message: types.Message, state: FSMContext):
    await state.update_data(full_name=message.text)
    await send_with_image(gnome_bot, message.from_user.id,
        "📞 Введите номер телефона (+79991234567):", "code")
    await state.set_state(GnomeReg.phone)

@gnome_dp.message(GnomeReg.phone)
async def reg_phone(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith('+') or not phone[1:].isdigit():
        await send_with_image(gnome_bot, message.from_user.id,
            "❌ Неверный формат. Введите +79991234567", "code")
        return
    await state.update_data(phone=phone)
    code = generate_sms_code(phone)
    send_sms(phone, code)
    await send_with_image(gnome_bot, message.from_user.id,
        f"📱 На номер {phone} отправлен код подтверждения. Введите его:", "code")
    await state.set_state(GnomeReg.waiting_code)

@gnome_dp.message(GnomeReg.waiting_code)
async def reg_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    phone = data.get('phone')
    if not verify_sms_code(phone, code):
        await send_with_image(gnome_bot, message.from_user.id,
            "❌ Неверный код. Попробуйте ещё раз.", "code")
        return
    await send_with_image(gnome_bot, message.from_user.id,
        "🏦 Введите название вашего банка:", "work")
    await state.set_state(GnomeReg.bank_name)

@gnome_dp.message(GnomeReg.bank_name)
async def reg_bank(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    ref_code = generate_ref_code(user_id)
    cur.execute('''
        INSERT INTO gnomes (telegram_id, full_name, phone, bank_name, ref_code, invited_by, verified, status)
        VALUES (?, ?, ?, ?, ?, ?, 1, 'active')
    ''', (user_id, data['full_name'], data['phone'], message.text, ref_code, data.get('invited_by')))
    conn.commit()
    if data.get('invited_by'):
        cur.execute('SELECT telegram_id FROM gnomes WHERE id = ?', (data['invited_by'],))
        inv = cur.fetchone()
        if inv:
            update_balance(inv[0], REFERRAL_BONUS)
            await gnome_bot.send_message(inv[0], f"🎉 +{REFERRAL_BONUS} ₽ за друга!")
    await send_with_image(gnome_bot, user_id,
        "✅ Регистрация завершена!", "success", gnome_kb)
    await state.clear()

@gnome_dp.message(F.text == "💰 Баланс")
async def gnome_balance(message: types.Message):
    if not is_verified(message.from_user.id):
        return await send_with_image(gnome_bot, message.from_user.id,
            "❌ Вы не прошли верификацию.", "code")
    await send_with_image(gnome_bot, message.from_user.id,
        f"💰 Баланс: {get_gnome_balance(message.from_user.id)} ₽", "balance")

@gnome_dp.message(F.text == "👥 Реферальная ссылка")
async def gnome_ref(message: types.Message):
    if not is_verified(message.from_user.id):
        return await send_with_image(gnome_bot, message.from_user.id,
            "❌ Вы не прошли верификацию.", "code")
    cur.execute('SELECT ref_code FROM gnomes WHERE telegram_id = ?', (message.from_user.id,))
    row = cur.fetchone()
    if row:
        link = f"https://t.me/{(await gnome_bot.get_me()).username}?start={row[0]}"
        await send_with_image(gnome_bot, message.from_user.id,
            f"👥 Ваша ссылка:\n{link}\n\n+{REFERRAL_BONUS} ₽ за друга!", "referral")

@gnome_dp.message(F.text == "📝 Отчёт")
async def gnome_report(message: types.Message, state: FSMContext):
    if not is_verified(message.from_user.id):
        return await send_with_image(gnome_bot, message.from_user.id,
            "❌ Вы не прошли верификацию.", "code")
    await send_with_image(gnome_bot, message.from_user.id,
        "📝 Введите сумму остатка:", "report")
    await state.set_state("waiting_report_amount")

@gnome_dp.message(F.text == "💼 Заработать")
async def gnome_work(message: types.Message, state: FSMContext):
    if not is_verified(message.from_user.id):
        return await send_with_image(gnome_bot, message.from_user.id,
            "❌ Вы не прошли верификацию.", "code")
    bank_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ОТП", callback_data="bank_otp")],
        [InlineKeyboardButton(text="Совкомбанк", callback_data="bank_sovkom")],
        [InlineKeyboardButton(text="Т-Банк", callback_data="bank_tbank")],
        [InlineKeyboardButton(text="Озон", callback_data="bank_ozon")],
        [InlineKeyboardButton(text="Альфа", callback_data="bank_alfa")]
    ])
    await send_with_image(gnome_bot, message.from_user.id,
        "🏦 Выберите банк:", "work", bank_kb)
    await state.set_state(WorkRequestStates.waiting_bank)

@gnome_dp.callback_query(WorkRequestStates.waiting_bank, F.data.startswith("bank_"))
async def gnome_work_bank(callback: types.CallbackQuery, state: FSMContext):
    bank = callback.data.split("_")[1].capitalize()
    await state.update_data(bank=bank)
    await callback.message.edit_caption("📞 Введите номер телефона, к которому привязан банк:")
    await state.set_state(WorkRequestStates.waiting_phone)
    await callback.answer()

@gnome_dp.message(WorkRequestStates.waiting_phone)
async def gnome_work_phone(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute('''
        INSERT INTO work_requests (user_id, bank, phone, status)
        VALUES (?, ?, ?, 'pending')
    ''', (message.from_user.id, data['bank'], message.text))
    conn.commit()
    await send_with_image(gnome_bot, message.from_user.id,
        "✅ Заявка на работу отправлена администратору!", "success")
    await state.clear()

@gnome_dp.message(F.text == "💸 Вывод средств")
async def gnome_withdraw(message: types.Message, state: FSMContext):
    if not is_verified(message.from_user.id):
        return await send_with_image(gnome_bot, message.from_user.id,
            "❌ Вы не прошли верификацию.", "code")
    await send_with_image(gnome_bot, message.from_user.id,
        "💰 Введите сумму вывода:", "withdraw")
    await state.set_state(WithdrawStates.waiting_amount)

@gnome_dp.message(WithdrawStates.waiting_amount)
async def withdraw_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        balance = get_gnome_balance(message.from_user.id)
        if amount > balance:
            await send_with_image(gnome_bot, message.from_user.id,
                f"❌ Недостаточно средств. Баланс: {balance} ₽", "withdraw")
            return
        await state.update_data(amount=amount)
        await send_with_image(gnome_bot, message.from_user.id,
            "📞 Введите номер телефона для вывода:", "withdraw")
        await state.set_state(WithdrawStates.waiting_phone)
    except:
        await send_with_image(gnome_bot, message.from_user.id,
            "❌ Введите число", "withdraw")

@gnome_dp.message(WithdrawStates.waiting_phone)
async def withdraw_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await send_with_image(gnome_bot, message.from_user.id,
        "🏦 Введите банк получателя:", "withdraw")
    await state.set_state(WithdrawStates.waiting_bank)

@gnome_dp.message(WithdrawStates.waiting_bank)
async def withdraw_bank(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute('''
        INSERT INTO withdrawal_requests (user_id, amount, phone, bank_name, status)
        VALUES (?, ?, ?, ?, 'pending')
    ''', (message.from_user.id, data['amount'], data['phone'], message.text))
    conn.commit()
    reduce_balance(message.from_user.id, data['amount'])
    await send_with_image(gnome_bot, message.from_user.id,
        f"✅ Заявка на вывод {data['amount']} ₽ отправлена! Средства заблокированы.", "success")
    await state.clear()

@gnome_dp.message(F.text == "✅ Пришли деньги")
async def gnome_money_received(message: types.Message, state: FSMContext):
    await send_with_image(gnome_bot, message.from_user.id,
        "💰 Введите сумму, которая пришла на карту:", "deal")
    await state.set_state(DealStates.waiting_amount)

@gnome_dp.message(DealStates.waiting_amount)
async def deal_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        await state.update_data(amount=amount)
        await send_with_image(gnome_bot, message.from_user.id,
            "💳 Введите текущий баланс карты:", "deal")
        await state.set_state(DealStates.waiting_balance)
    except:
        await send_with_image(gnome_bot, message.from_user.id,
            "❌ Введите число", "deal")

@gnome_dp.message(DealStates.waiting_balance)
async def deal_balance(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cur.execute('SELECT id FROM deals WHERE gnome_id = (SELECT id FROM gnomes WHERE telegram_id = ?) AND status = "waiting_payment" ORDER BY id DESC LIMIT 1', (message.from_user.id,))
    deal = cur.fetchone()
    if deal:
        cur.execute('UPDATE deals SET status = "completed" WHERE id = ?', (deal[0],))
        conn.commit()
    await send_with_image(gnome_bot, message.from_user.id,
        "✅ Информация отправлена администратору!", "success")
    await admin_bot.send_message(MASTER_ID, f"💰 Гном {get_gnome_name(message.from_user.id)} сообщил о поступлении {data['amount']} ₽. Баланс карты: {message.text} ₽")
    await state.clear()

@gnome_dp.message(F.text == "❌ Не приходят")
async def gnome_money_not_received(message: types.Message):
    await send_with_image(gnome_bot, message.from_user.id,
        "⏳ Ожидайте, администратор проверит статус платежа.", "deal")
    await admin_bot.send_message(MASTER_ID, f"⚠️ Гном {get_gnome_name(message.from_user.id)} сообщил, что деньги не пришли.")

# ========== АДМИН-БОТ ==========
def is_admin_verified(telegram_id):
    if telegram_id == MASTER_ID:
        return True
    cur.execute('SELECT is_verified FROM admins WHERE telegram_id = ?', (telegram_id,))
    row = cur.fetchone()
    return row and row[0] == 1

def mark_admin_verified(telegram_id):
    cur.execute('INSERT OR REPLACE INTO admins (telegram_id, is_verified) VALUES (?, 1)', (telegram_id,))
    conn.commit()

@admin_dp.message(Command("start"))
async def admin_start(message: types.Message, state: FSMContext):
    if is_admin_verified(message.from_user.id):
        await message.answer("👑 Админ-панель", reply_markup=admin_kb)
        return
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
        mark_admin_verified(message.from_user.id)
        await message.answer("✅ Вход выполнен!", reply_markup=admin_kb)
        await state.clear()
    else:
        await message.answer("❌ Неверный пароль")

@admin_dp.message(F.text == "📋 Заявки на работу")
async def admin_requests(message: types.Message):
    if not is_admin_verified(message.from_user.id): return
    cur.execute('SELECT id, user_id, bank, phone FROM work_requests WHERE status = "pending"')
    rows = cur.fetchall()
    if not rows:
        await message.answer("📭 Нет заявок")
        return
    for r in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять", callback_data=f"work_accept_{r[0]}_{r[1]}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"work_reject_{r[0]}")]
        ])
        await message.answer(f"📝 Заявка\n👤 {get_gnome_name(r[1])}\n🏦 {r[2]}\n📞 {r[3]}", reply_markup=kb)

@admin_dp.callback_query(F.data.startswith("work_accept_"))
async def work_accept(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    req_id = int(parts[2])
    user_id = int(parts[3])
    cur.execute('UPDATE work_requests SET status = "approved" WHERE id = ?', (req_id,))
    set_work_status(user_id, 'working')
    conn.commit()
    await callback.message.edit_text("✅ Гном принят в работу")
    await gnome_bot.send_message(user_id, "✅ Вы приняты в работу! Теперь вы можете получать сделки.")
    await callback.answer()

@admin_dp.callback_query(F.data.startswith("work_reject_"))
async def work_reject(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    cur.execute('UPDATE work_requests SET status = "rejected" WHERE id = ?', (req_id,))
    conn.commit()
    await callback.message.edit_text("❌ Заявка отклонена")
    await callback.answer()

@admin_dp.message(F.text == "🤝 Взаимодействовать")
async def admin_interact(message: types.Message):
    if not is_admin_verified(message.from_user.id): return
    await message.answer("🤝 Выберите действие:", reply_markup=interact_kb)

@admin_dp.message(F.text == "📤 Отправить реквизиты")
async def admin_send_requisites(message: types.Message, state: FSMContext):
    await message.answer("📝 Введите реквизиты в формате:\n+79788591615\nСБЕРБАНК\n1000")
    await state.set_state(AdminStates.waiting_requisites)

@admin_dp.message(AdminStates.waiting_requisites)
async def admin_requisites_text(message: types.Message, state: FSMContext):
    await message.answer("✅ Реквизиты сохранены. Отправьте их нужному гному командой /send_requisites @username")
    await state.clear()

@admin_dp.message(F.text == "💰 Отправить сделку")
async def admin_send_deal(message: types.Message, state: FSMContext):
    await message.answer("📝 Введите текст сделки:")
    await state.set_state(AdminStates.waiting_deal_text)

@admin_dp.message(AdminStates.waiting_deal_text)
async def admin_deal_text(message: types.Message, state: FSMContext):
    await state.update_data(deal_text=message.text)
    working_gnomes = get_working_gnomes()
    if not working_gnomes:
        await message.answer("❌ Нет гномов в работе")
        await state.clear()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for gnome_id, name in working_gnomes:
        kb.inline_keyboard.append([InlineKeyboardButton(text=name, callback_data=f"send_deal_{gnome_id}")])
    await message.answer("👥 Выберите гнома для отправки сделки:", reply_markup=kb)
    await state.set_state(AdminStates.waiting_gnome_selection)

@admin_dp.callback_query(AdminStates.waiting_gnome_selection, F.data.startswith("send_deal_"))
async def admin_send_deal_to_gnome(callback: types.CallbackQuery, state: FSMContext):
    gnome_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    cur.execute('INSERT INTO deals (gnome_id, deal_text, status) VALUES (?, ?, "waiting_payment")', (gnome_id, data['deal_text']))
    conn.commit()
    await gnome_bot.send_message(gnome_id, f"🆕 **Новая сделка!**\n\n{data['deal_text']}\n\nПосле поступления денег нажмите «Пришли деньги»", reply_markup=gnome_deal_kb)
    await callback.message.edit_text(f"✅ Сделка отправлена гному {get_gnome_name(gnome_id)}")
    await state.clear()
    await callback.answer()

@admin_dp.message(F.text == "💸 Заявки на вывод")
async def admin_withdraw_requests(message: types.Message):
    if not is_admin_verified(message.from_user.id): return
    cur.execute('SELECT id, user_id, amount, phone, bank_name FROM withdrawal_requests WHERE status = "pending"')
    rows = cur.fetchall()
    if not rows:
        await message.answer("📭 Нет заявок на вывод")
        return
    for r in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выплачено", callback_data=f"withdraw_accept_{r[0]}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"withdraw_reject_{r[0]}")]
        ])
        await message.answer(f"💸 Заявка на вывод\n👤 {get_gnome_name(r[1])}\n💰 {r[2]} ₽\n📞 {r[3]}\n🏦 {r[4]}", reply_markup=kb)

@admin_dp.callback_query(F.data.startswith("withdraw_accept_"))
async def withdraw_accept(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    cur.execute('UPDATE withdrawal_requests SET status = "approved" WHERE id = ?', (req_id,))
    conn.commit()
    await callback.message.edit_text("✅ Вывод подтверждён")
    await callback.answer()

@admin_dp.callback_query(F.data.startswith("withdraw_reject_"))
async def withdraw_reject(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[2])
    cur.execute('UPDATE withdrawal_requests SET status = "rejected" WHERE id = ?', (req_id,))
    cur.execute('SELECT user_id, amount FROM withdrawal_requests WHERE id = ?', (req_id,))
    row = cur.fetchone()
    if row:
        update_balance(row[0], row[1])
        await gnome_bot.send_message(row[0], f"❌ Заявка на вывод отклонена. {row[1]} ₽ возвращены на баланс.")
    await callback.message.edit_text("❌ Вывод отклонён")
    await callback.answer()

@admin_dp.message(F.text == "👥 Все гномы")
async def admin_gnomes(message: types.Message):
    if not is_admin_verified(message.from_user.id): return
    cur.execute('SELECT full_name, phone, balance, work_status FROM gnomes WHERE status = "active"')
    rows = cur.fetchall()
    if not rows:
        await message.answer("📭 Нет гномов")
        return
    text = "🧑‍🌾 Гномы:\n\n"
    for r in rows:
        status_work = "🔧 В работе" if r[3] == "working" else "⏳ Ожидает"
        text += f"✅ {r[0]} | {r[1]} | баланс: {r[2]} ₽ | {status_work}\n"
    await message.answer(text)

@admin_dp.message(F.text == "💰 Начислить деньги")
async def admin_pay_start(message: types.Message, state: FSMContext):
    if not is_admin_verified(message.from_user.id): return
    await message.answer("💰 Введите ID и сумму: 8523282279 500")
    await state.set_state(AdminStates.waiting_amount)

@admin_dp.message(AdminStates.waiting_amount, F.text)
async def admin_pay_process(message: types.Message, state: FSMContext):
    try:
        user_id, amount = map(int, message.text.split())
        cur.execute('SELECT full_name FROM gnomes WHERE telegram_id = ?', (user_id,))
        row = cur.fetchone()
        if not row:
            await message.answer("❌ Гном не найден")
            return
        update_balance(user_id, amount)
        await message.answer(f"✅ Начислено {amount} ₽ {row[0]}")
        await gnome_bot.send_message(user_id, f"💰 Начислено {amount} ₽!")
    except:
        await message.answer("❌ Ошибка")
    await state.clear()

@admin_dp.message(F.text == "📊 Статистика")
async def admin_stats(message: types.Message):
    cur.execute('SELECT COUNT(*) FROM gnomes')
    total = cur.fetchone()[0]
    cur.execute('SELECT SUM(balance) FROM gnomes')
    bal = cur.fetchone()[0] or 0
    cur.execute('SELECT COUNT(*) FROM work_requests WHERE status = "pending"')
    pending = cur.fetchone()[0]
    await message.answer(f"📊 Гномов: {total}\n💰 Общий баланс: {bal} ₽\n⏳ Заявок: {pending}")

async def main():
    print("✅ Боты запущены")
    await asyncio.gather(
        gnome_dp.start_polling(gnome_bot),
        admin_dp.start_polling(admin_bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
