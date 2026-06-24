import asyncio

import aiosqlite

from datetime import datetime

from aiogram import Bot, Dispatcher, types, F

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from aiogram.filters import Command

TOKEN = "8992460588:AAG8hv3Q3Lfm0lRW43SL9amI6HKfVT1Kx7A"

ADMINS = [2053617850]

ADMINS = [89299392789]

bot = Bot(token=TOKEN)

dp = Dispatcher()

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

# ================= UI =================

def menu():

    return InlineKeyboardMarkup(inline_keyboard=[

        [InlineKeyboardButton(text="👥 Состав", callback_data="players")],

        [InlineKeyboardButton(text="📥 Заявки", callback_data="apps")],

        [InlineKeyboardButton(text="⚔️ КВ", callback_data="cw")],

        [InlineKeyboardButton(text="📊 Стата", callback_data="stats")],

        [InlineKeyboardButton(text="💰 UC Магазин", callback_data="shop")]

    ])

# ================= START =================

@dp.message(Command("start"))

async def start(msg: types.Message):

    await msg.answer("🔥 2PIK BOT", reply_markup=menu())

# ================= PLAYERS =================

@dp.callback_query(F.data == "players")

async def players(call: types.CallbackQuery):

    async with aiosqlite.connect(DB) as db:

        rows = await db.execute_fetchall("SELECT nickname, role FROM players")

    text = "👥 Состав:\n\n"

    for r in rows:

        text += f"{r[0]} — {r[1]}\n"

    await call.message.edit_text(text, reply_markup=menu())

# ================= JOIN =================

user_state = {}

@dp.message(Command("join"))

async def join(msg: types.Message):

    user_state[msg.from_user.id] = {}

    await msg.answer("Введите ник:")

@dp.message()

async def form(msg: types.Message):

    if msg.from_user.id not in user_state:

        return

    data = user_state[msg.from_user.id]

    if "nickname" not in data:

        data["nickname"] = msg.text

        await msg.answer("PUBG ID:")

        return

    if "pubg_id" not in data:

        data["pubg_id"] = msg.text

        await msg.answer("Ранг:")

        return

    if "rank" not in data:

        data["rank"] = msg.text

        async with aiosqlite.connect(DB) as db:

            cursor = await db.execute(

                "INSERT INTO applications (tg_id, nickname, pubg_id, rank, status) VALUES (?, ?, ?, ?, ?)",

                (msg.from_user.id, data["nickname"], data["pubg_id"], data["rank"], "pending")

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

                f"📥 Заявка\n{data['nickname']} ({data['rank']})\nID: {data['pubg_id']}",

                reply_markup=kb

            )

        await msg.answer("Заявка отправлена ✅")

        del user_state[msg.from_user.id]

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

# ================= CW =================

@dp.callback_query(F.data == "cw")

async def cw(call: types.CallbackQuery):

    async with aiosqlite.connect(DB) as db:

        rows = await db.execute_fetchall("SELECT enemy, time FROM cw")

    text = "⚔️ КВ:\n\n"

    for r in rows:

        text += f"VS {r[0]} — {r[1]}\n"

    await call.message.edit_text(text, reply_markup=menu())

# ================= ADD CW =================

@dp.message(Command("add_cw"))

async def add_cw(msg: types.Message):

    if msg.from_user.id not in ADMINS:

        return

    _, enemy, time = msg.text.split(maxsplit=2)

    async with aiosqlite.connect(DB) as db:

        await db.execute(

            "INSERT INTO cw (enemy, time) VALUES (?, ?)",

            (enemy, time)

        )

        await db.commit()

    await msg.answer("КВ добавлено ⚔️")

# ================= ACTIVE =================

@dp.message(Command("active"))

async def active(msg: types.Message):

    async with aiosqlite.connect(DB) as db:

        await db.execute(

            "UPDATE players SET last_active=? WHERE tg_id=?",

            (str(datetime.now()), msg.from_user.id)

        )

        await db.commit()

    await msg.answer("Актив ✅")

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

# ================= WIN =================

@dp.message(Command("win"))

async def win(msg: types.Message):

    async with aiosqlite.connect(DB) as db:

        await db.execute(

            "UPDATE players SET wins = wins + 1 WHERE tg_id=?",

            (msg.from_user.id,)

        )

        await db.commit()

    await msg.answer("Победа 🏆")

# ================= SHOP =================

@dp.callback_query(F.data == "shop")

async def shop(call: types.CallbackQuery):

    await call.message.edit_text(

        "💰 Напиши: /buy_uc 660\n",

        reply_markup=menu()

    )

@dp.message(Command("buy_uc"))

async def buy(msg: types.Message):

    _, amount = msg.text.split()

    async with aiosqlite.connect(DB) as db:

        await db.execute(

            "INSERT INTO shop (user_id, amount, status) VALUES (?, ?, ?)",

            (msg.from_user.id, amount, "pending")

        )

        await db.commit()

    await msg.answer("Заявка на UC отправлена 💰")

# ================= RUN =================

async def main():

    await init_db()

    await dp.start_polling(bot)

asyncio.run(main())
