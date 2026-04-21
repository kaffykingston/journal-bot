import os
import aiosqlite
import logging
import traceback
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Set BOT_TOKEN environment variable")

conn = None

# ---------------- DATABASE ----------------
async def init_db():
    global conn
    conn = await aiosqlite.connect("trades.db")
    cursor = await conn.cursor()
    await cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT,
        rr REAL,
        result TEXT,
        emotion TEXT,
        notes TEXT,
        raw_text TEXT
    )
    """)
    await conn.commit()

# ---------------- MESSAGE HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # ✅ ignore non-text messages
        if not update.message or not update.message.text:
            return

        text = update.message.text.lower()

        pair = "unknown"
        rr = 0
        result = "unknown"
        emotion = "unknown"

        # ---- PAIR ----
        if "gj" in text or "gbpjpy" in text:
            pair = "GBPJPY"
        elif "eu" in text or "eurusd" in text:
            pair = "EURUSD"

        # ---- RR ----
        import re
        rr_match = re.search(r'1:(\d+)', text)
        if rr_match:
            rr = float(rr_match.group(1))

        # ---- RESULT ----
        if "win" in text:
            result = "win"
        elif "loss" in text:
            result = "loss"

        # ---- EMOTION ----
        if "fear" in text:
            emotion = "fear"
        elif "calm" in text:
            emotion = "calm"
        elif "greed" in text:
            emotion = "greed"

        # ---- SAVE ----
        cursor = await conn.cursor()
        await cursor.execute("""
        INSERT INTO trades (pair, rr, result, emotion, notes, raw_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (pair, rr, result, emotion, "", text))

        await conn.commit()

        await update.message.reply_text(
            f"Saved ✅\nPair: {pair}\nRR: {rr}\nResult: {result}"
        )

    except Exception:
        traceback.print_exc()
        await update.message.reply_text("Error occurred ❌")

# ---------------- REPORT ----------------
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = await conn.cursor()
    await cursor.execute("SELECT pair, rr, result FROM trades")
    rows = await cursor.fetchall()

    if not rows:
        await update.message.reply_text("No trades yet ❌")
        return

    total = len(rows)
    wins = sum(1 for _, _, r in rows if r == "win")
    win_rate = (wins / total) * 100

    await update.message.reply_text(
        f"📊 Trades: {total}\nWin rate: {win_rate:.2f}%"
    )

# ---------------- START ----------------
async def on_startup(app):
    await init_db()

app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CommandHandler("report", report))

print("Bot running...")
app.run_polling()