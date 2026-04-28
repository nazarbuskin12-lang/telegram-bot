import asyncio
import sqlite3
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
# =======================================

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
        verified INTEGER DEFAULT 0,
        verification_photo TEXT,
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
    CREATE TABLE IF NOT EXISTS daily_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount INTEGER,
        date DATE
    );
    CREATE TABLE IF NOT EXISTS admins (
        telegram_id INTEGER PRIMARY KEY,
        is_verified INTEGER DEFAULT 0
    );
''')
conn.commit()

class GnomeReg(StatesGroup):
    full_name = State()
    phone = State()
    card_number = State()
    bank_name = State()
    verification_photo = State()

class WorkRequest(StatesGroup):
    waiting_bank = State()

class AdminAuth(StatesGroup):
    waiting_login = State()
    waiting_password = State()

class AdminStates(StatesGroup):
    waiting_amount = State()

gnome_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💰 Баланс"), KeyboardButton(text="👥 Реферальная ссылка")],
        [KeyboardButton(text="📝 Отчёт"), KeyboardButton(text="💼 Заработать")]
    ],
    resize_keyboard=True
)

admin_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Заявки на работу")],
        [KeyboardButton(text="👥 Все гномы")],
        [KeyboardButton(text="🆕 Новые верификации")],
        [KeyboardButton(text="💰 Начислить деньги")],
        [KeyboardButton(text="📊 Статистика")]
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
        await message.answer("🌟 Добро пожаловать! Введите ФИО:")
        await state.set_state(GnomeReg.full_name)
    elif is_verified(user_id):
        name = get_gnome_name(user_id)
        await message.answer(f"👋 С возвращением, {name}!", reply_markup=gnome_kb)
    else:
        await message.answer(f"⏳ Привет, {user[2]}! Верификация ещё не пройдена.")

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
    await state.update_data(bank_name=message.text)
    await message.answer("📸 Отправьте фото паспорта рядом с лицом:")
    await state.set_state(GnomeReg.verification_photo)

@gnome_dp.message(GnomeReg.verification_photo, F.photo)
async def reg_verification(message: types.Message, state: FSMContext):
    photo = message.photo[-1]
    data = await state.get_data()
    user_id = message.from_user.id
    ref_code = generate_ref_code(user_id)
    
    cur.execute('''
        INSERT INTO gnomes (telegram_id, full_name, phone, card_number, bank_name, ref_code, invited_by, verification_photo, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
    ''', (user_id, data['full_name'], data['phone'], data['card_number'], data['bank_name'], ref_code, data.get('invited_by'), photo.file_id))
    conn.commit()
    
    if data.get('invited_by'):
        cur.execute('SELECT telegram_id FROM gnomes WHERE id = ?', (data['invited_by'],))
        inv = cur.fetchone()
        if inv:
            update_balance(inv[0], REFERRAL_BONUS)
            await gnome_bot.send_message(inv[0], f"🎉 +{REFERRAL_BONUS} ₽ за друга!")
    
    # Отправляем уведомление в АДМИН-БОТА
    await admin_bot.send_message(MASTER_ID, f"🆕 Новая верификация от {data['full_name']}\nID: {user_id}")
    await message.answer("✅ Фото отправлено на проверку.")
    await state.clear()

@gnome_dp.message(F.text == "💰 Баланс")
async def gnome_balance(message: types.Message):
    if not is_verified(message.from_user.id):
        await message.answer("❌ Вы не прошли верификацию.")
        return
    await message.answer(f"💰 {get_gnome_name(message.from_user.id)}, баланс: {get_gnome_balance(message.from_user.id)} ₽")

@gnome_dp.message(F.text == "👥 Реферальная ссылка")
async def gnome_ref(message: types.Message):
    if not is_verified(message.from_user.id):
        await message.answer("❌ Вы не прошли верификацию.")
        return
    cur.execute('SELECT ref_code FROM gnomes WHERE telegram_id = ?', (message.from_user.id,))
    row = cur.fetchone()
    if row:
        link = f"https://t.me/{(await gnome_bot.get_me()).username}?start={row[0]}"
        await message.answer(f"👥 Ваша ссылка:\n{link}\n\n+{REFERRAL_BONUS} ₽ за друга!")

@gnome_dp.message(F.text == "📝 Отчёт")
async def gnome_report(message: types.Message, state: FSMContext):
    if not is_verified(message.from_user.id):
        await message.answer("❌ Вы не прошли верификацию.")
        return
    await message.answer("📝 Введите сумму остатка:")
    await state.set_state("waiting_report_amount")

@gnome_dp.message(lambda m: m.text.isdigit(), lambda m: m.state == "waiting_report_amount")
async def gnome_report_amount(message: types.Message, state: FSMContext):
    amount = int(message.text)
    cur.execute('INSERT INTO daily_reports (user_id, amount, date) VALUES (?, ?, DATE("now"))', (message.from_user.id, amount))
    conn.commit()
    await message.answer(f"✅ Отчёт на {amount} ₽ отправлен!")
    await state.clear()

@gnome_dp.message(F.text == "💼 Заработать")
async def gnome_work(message: types.Message, state: FSMContext):
    if not is_verified(message.from_user.id):
        await message.answer("❌ Вы не прошли верификацию.")
        return
    bank_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ОТП", callback_data="bank_otp")],
        [InlineKeyboardButton(text="Совкомбанк", callback_data="bank_sovkom")],
        [InlineKeyboardButton(text="Т-Банк", callback_data="bank_tbank")],
        [InlineKeyboardButton(text="Озон", callback_data="bank_ozon")],
        [InlineKeyboardButton(text="Альфа", callback_data="bank_alfa")]
    ])
    await message.answer("🏦 Выберите банк:", reply_markup=bank_kb)
    await state.set_state(WorkRequest.waiting_bank)

@gnome_dp.callback_query(WorkRequest.waiting_bank, F.data.startswith("bank_"))
async def gnome_work_bank(callback: types.CallbackQuery, state: FSMContext):
    bank = callback.data.split("_")[1].capitalize()
    cur.execute('INSERT INTO work_requests (user_id, bank) VALUES (?, ?)', (callback.from_user.id, bank))
    conn.commit()
    await callback.message.edit_text(f"✅ Заявка отправлена!")
    await state.clear()
    await callback.answer()

# ========== АДМИН-БОТ ==========
def is_admin_verified(telegram_id):
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
    cur.execute('SELECT id, user_id, bank FROM work_requests WHERE status = "pending"')
    rows = cur.fetchall()
    if not rows:
        await message.answer("📭 Нет заявок")
        return
    for r in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_{r[0]}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{r[0]}")]
        ])
        await message.answer(f"📝 Заявка #{r[0]}\nГном: {get_gnome_name(r[1])}\nБанк: {r[2]}", reply_markup=kb)

@admin_dp.callback_query(F.data.startswith("approve_"))
async def approve_work(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    cur.execute('SELECT user_id FROM work_requests WHERE id = ?', (req_id,))
    row = cur.fetchone()
    if row:
        cur.execute('UPDATE work_requests SET status = "approved" WHERE id = ?', (req_id,))
        conn.commit()
        await callback.message.edit_text("✅ Заявка одобрена")
        await gnome_bot.send_message(row[0], "✅ Ваша заявка одобрена!")
    await callback.answer()

@admin_dp.callback_query(F.data.startswith("reject_"))
async def reject_work(callback: types.CallbackQuery):
    req_id = int(callback.data.split("_")[1])
    cur.execute('SELECT user_id FROM work_requests WHERE id = ?', (req_id,))
    row = cur.fetchone()
    if row:
        cur.execute('UPDATE work_requests SET status = "rejected" WHERE id = ?', (req_id,))
        conn.commit()
        await callback.message.edit_text("❌ Заявка отклонена")
        await gnome_bot.send_message(row[0], "❌ Заявка отклонена")
    await callback.answer()

@admin_dp.message(F.text == "🆕 Новые верификации")
async def admin_new_verifications(message: types.Message):
    if not is_admin_verified(message.from_user.id) and message.from_user.id != MASTER_ID:
        await message.answer("⛔ Нет доступа.")
        return
    
    cur.execute('SELECT id, telegram_id, full_name, verification_photo FROM gnomes WHERE verified = 0 AND status = "pending"')
    pending = cur.fetchall()
    
    if not pending:
        await message.answer("📭 Нет новых верификаций")
        return
    
    for p in pending:
        gnome_id, telegram_id, full_name, photo_id = p
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"verify_accept_{telegram_id}"),
             InlineKeyboardButton(text="❌ Отклонить", callback_data=f"verify_reject_{telegram_id}")]
        ])
        await admin_bot.send_photo(
            message.from_user.id,
            photo_id,
            caption=f"🆕 **Заявка на верификацию**\n\n👤 Гном: {full_name}\n🆔 ID: {telegram_id}",
            reply_markup=kb
        )

@admin_dp.callback_query(F.data.startswith("verify_accept_"))
async def admin_verify_accept(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    cur.execute('UPDATE gnomes SET verified = 1, status = "active" WHERE telegram_id = ?', (user_id,))
    conn.commit()
    name = get_gnome_name(user_id)
    await callback.message.edit_caption(f"✅ {name} — верификация подтверждена")
    await gnome_bot.send_message(user_id, f"✅ {name}, вы верифицированы! Теперь вы можете работать.")
    await callback.answer()

@admin_dp.callback_query(F.data.startswith("verify_reject_"))
async def admin_verify_reject(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[2])
    cur.execute('DELETE FROM gnomes WHERE telegram_id = ?', (user_id,))
    conn.commit()
    await callback.message.edit_caption(f"❌ Гном {user_id} удалён")
    await callback.answer()

@admin_dp.message(F.text == "👥 Все гномы")
async def admin_gnomes(message: types.Message):
    cur.execute('SELECT full_name, phone, balance, verified FROM gnomes WHERE status = "active"')
    rows = cur.fetchall()
    if not rows:
        await message.answer("📭 Нет гномов")
        return
    text = "🧑‍🌾 Гномы:\n\n"
    for r in rows:
        text += f"{'✅' if r[3] else '⏳'} {r[0]} | {r[1]} | {r[2]} ₽\n"
    await message.answer(text)

@admin_dp.message(F.text == "💰 Начислить деньги")
async def admin_pay_start(message: types.Message, state: FSMContext):
    await message.answer("💰 Введите ID гнома и сумму:\nПример: 8523282279 500")
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
        await gnome_bot.send_message(user_id, f"💰 +{amount} ₽!")
    except:
        await message.answer("❌ Формат: ID_гнома сумма")
    await state.clear()

@admin_dp.message(F.text == "📊 Статистика")
async def admin_stats(message: types.Message):
    cur.execute('SELECT COUNT(*) FROM gnomes')
    total = cur.fetchone()[0]
    cur.execute('SELECT SUM(balance) FROM gnomes')
    bal = cur.fetchone()[0] or 0
    cur.execute('SELECT COUNT(*) FROM work_requests WHERE status = "pending"')
    pending = cur.fetchone()[0]
    await message.answer(f"📊 Гномов: {total}\n💰 Баланс: {bal} ₽\n⏳ Заявок: {pending}")

# ========== ЗАПУСК ==========
async def main():
    print("✅ Боты запущены")
    await asyncio.gather(
        gnome_dp.start_polling(gnome_bot),
        admin_dp.start_polling(admin_bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
