import asyncio

import os

import aiosqlite

from datetime import datetime

from aiogram import Bot, Dispatcher, types, F

from aiogram.filters import Command

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.fsm.state import StatesGroup, State

from aiogram.fsm.context import FSMContext

from aiogram.fsm.storage.memory import MemoryStorage

TOKEN = "8992460588:AAG8hv3Q3Lfm0lRW43SL9amI6HKfVT1Kx7A"

ADMINS = [2053617850]

bot = Bot(token=TOKEN)

dp = Dispatcher(storage=MemoryStorage())

DB = "clan.db"

# ================= DB =================

async def init_db():

    async with aiosqlite.connect(DB) as db:

        await db.execute("""

        CREATE TABLE IF NOT EXISTS players (

            id INTEGER PRIMARY KEY,

            tg_id INTEGER,

            nickname TEXT,

            pubg_id TEXT,

            role TEXT,

            wins INTEGER DEFAULT 0,

            loses INTEGER DEFAULT 0,

            last_active TEXT

        )

        """)

        await db.execute("""

        CREATE TABLE IF NOT EXISTS applications (

            id INTEGER PRIMARY KEY,

            tg_id INTEGER,

            nickname TEXT,

            pubg_id TEXT,

            rank TEXT,

            status TEXT

        )

        """)

        await db.execute("""

        CREATE TABLE IF NOT EXISTS cw (

            id INTEGER PRIMARY KEY,

            enemy TEXT,

            time TEXT

        )

        """)

        await db.execute("""

        CREATE TABLE IF NOT EXISTS shop (

            id INTEGER PRIMARY KEY,

            user_id INTEGER,

            amount TEXT,

            status TEXT

        )

        """)

        await db.commit()

# ================= FSM =================

class JoinState(StatesGroup):

    nickname = State()

    pubg_id = State()

    rank = State()

# ================= UI =================

def menu():

    return InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text="👥 Состав", callback_data="players")],

        [InlineKeyboardButton(text="⚔️ КВ", callback_data="cw")],

        [InlineKeyboardButton(text="📊 Стата", callback_data="stats")],

        [InlineKeyboardButton(text="💰 UC", callback_data="shop")]

    ])

# ================= START =================

@dp.message(Command("start"))

async def start(msg: types.Message):

    await msg.answer("🔥 2PIK BOT", reply_markup=menu())

# ================= JOIN FSM =================

@dp.message(Command("join"))

async def join_start(msg: types.Message, state: FSMContext):

    await state.set_state(JoinState.nickname)

    await msg.answer("Введите ник:")

@dp.message(JoinState.nickname)

async def join_nick(msg: types.Message, state: FSMContext):

    await state.update_data(nickname=msg.text)

    await state.set_state(JoinState.pubg_id)

    await msg.answer("PUBG ID:")

@dp.message(JoinState.pubg_id)

async def join_id(msg: types.Message, state: FSMContext):

    await state.update_data(pubg_id=msg.text)

    await state.set_state(JoinState.rank)

    await msg.answer("Ранг:")

@dp.message(JoinState.rank)

async def join_finish(msg: types.Message, state: FSMContext):

    data = await state.get_data()

    async with aiosqlite.connect(DB) as db:

        cursor = await db.execute(

            "INSERT INTO applications (tg_id, nickname, pubg_id, rank, status) VALUES (?, ?, ?, ?, ?)",

            (msg.from_user.id, data["nickname"], data["pubg_id"], msg.text, "pending")

        )

        app_id = cursor.lastrowid

        await db.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[

        [

            InlineKeyboardButton(text="✅", callback_data=f"accept_{app_id}"),

            InlineKeyboardButton(text="❌", callback_data=f"reject_{app_id}")

        ]

    ])

    for admin in ADMINS:

        await bot.send_message(

            admin,

            f"📥 {data['nickname']} ({msg.text})\nID: {data['pubg_id']}",

            reply_markup=kb

        )

    await msg.answer("Заявка отправлена ✅")

    await state.clear()

# ================= ACCEPT =================

def get_role(rank):

    if "Ace" in rank:

        return "Main"

    elif "Crown" in rank:

        return "Academy"

    return "Recruit"

@dp.callback_query(F.data.startswith("accept_"))

async def accept(call: types.CallbackQuery):

    if call.from_user.id not in ADMINS:

        return

    app_id = int(call.data.split("_")[1])

    async with aiosqlite.connect(DB) as db:

        app = await db.execute_fetchone(

            "SELECT tg_id, nickname, pubg_id, rank FROM applications WHERE id=?",

            (app_id,)

        )

        role = get_role(app[3])

        await db.execute(

            "INSERT INTO players (tg_id, nickname, pubg_id, role) VALUES (?, ?, ?, ?)",

            (app[0], app[1], app[2], role)

        )

        await db.execute("UPDATE applications SET status='accepted' WHERE id=?", (app_id,))

        await db.commit()

    await call.message.edit_text("✅ Принято")

# ================= REJECT =================

@dp.callback_query(F.data.startswith("reject_"))

async def reject(call: types.CallbackQuery):

    if call.from_user.id not in ADMINS:

        return

    app_id = int(call.data.split("_")[1])

    async with aiosqlite.connect(DB) as db:

        await db.execute("UPDATE applications SET status='rejected' WHERE id=?", (app_id,))

        await db.commit()

    await call.message.edit_text("❌ Отклонено")

# ================= PLAYERS =================

@dp.callback_query(F.data == "players")

async def players(call: types.CallbackQuery):

    async with aiosqlite.connect(DB) as db:

        rows = await db.execute_fetchall("SELECT nickname, role FROM players")

    text = "👥 Состав:\n\n"

    for r in rows:

        text += f"{r[0]} — {r[1]}\n"

    await call.message.edit_text(text, reply_markup=menu())

# ================= CW =================

@dp.callback_query(F.data == "cw")

async def cw(call: types.CallbackQuery):

    async with aiosqlite.connect(DB) as db:

        rows = await db.execute_fetchall("SELECT enemy, time FROM cw")

    text = "⚔️ КВ:\n\n"

    for r in rows:

        text += f"VS {r[0]} — {r[1]}\n"

    await call.message.edit_text(text, reply_markup=menu())

@dp.message(Command("add_cw"))

async def add_cw(msg: types.Message):

    if msg.from_user.id not in ADMINS:

        return

    _, enemy, time = msg.text.split(maxsplit=2)

    async with aiosqlite.connect(DB) as db:

        await db.execute("INSERT INTO cw (enemy, time) VALUES (?, ?)", (enemy, time))

        await db.commit()

    await msg.answer("КВ добавлено ⚔️")

# ================= STATS =================

@dp.callback_query(F.data == "stats")

async def stats(call: types.CallbackQuery):

    async with aiosqlite.connect(DB) as db:

        rows = await db.execute_fetchall(

            "SELECT nickname, wins, loses FROM players"

        )

    text = "📊 Стата:\n\n"

    for r in rows:

        text += f"{r[0]} | 🏆 {r[1]} | ❌ {r[2]}\n"

    await call.message.edit_text(text, reply_markup=menu())

# ================= ACTIVE =================

@dp.message(Command("active"))

async def active(msg: types.Message):

    async with aiosqlite.connect(DB) as db:

        await db.execute(

            "UPDATE players SET last_active=? WHERE tg_id=?",

            (str(datetime.now()), msg.from_user.id)

        )

        await db.commit()

    await msg.answer("Актив засчитан ✅")

# ================= SHOP =================

@dp.callback_query(F.data == "shop")

async def shop(call: types.CallbackQuery):

    await call.message.edit_text("💰 /buy_uc 660", reply_markup=menu())

@dp.message(Command("buy_uc"))

async def buy(msg: types.Message):

    _, amount = msg.text.split()

    async with aiosqlite.connect(DB) as db:

        await db.execute(

            "INSERT INTO shop (user_id, amount, status) VALUES (?, ?, ?)",

            (msg.from_user.id, amount, "pending")

        )

        await db.commit()

    await msg.answer("Заявка отправлена 💰")

# ================= RUN =================

async def main():

    await init_db()

    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())
