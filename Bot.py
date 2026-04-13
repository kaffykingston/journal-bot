import os
import aiosqlite
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes
)

# ---------------- CONFIG ----------------
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
        text = update.message.text
        lines = text.split("\n")

        data = {}

        # parse input
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip().lower()] = value.strip()

        # required fields
        pair = data.get("pair")
        rr_raw = data.get("rr")
        result = data.get("result")

        # optional fields
        emotion = data.get("emotion", "")
        notes = data.get("notes", "")

        if not pair or not rr_raw or not result:
            await update.message.reply_text(
                "Format error ❌\nUse:\nPair: GBPJPY\nRR: 1:5\nResult: Win"
            )
            return

        # convert RR safely
        try:
            if ":" in rr_raw:
                a, b = rr_raw.split(":")
                rr = float(b) / float(a)
            else:
                rr = float(rr_raw)
        except:
            rr = 0.0

        cursor = await conn.cursor()
        await cursor.execute("""
        INSERT INTO trades (pair, rr, result, emotion, notes, raw_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (pair, rr, result, emotion, notes, text))

        await conn.commit()

        await update.message.reply_text("Trade saved ✅")

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("Something went wrong ❌")

# ---------------- REPORT ----------------
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor = await conn.cursor()
    await cursor.execute("SELECT pair, rr, result FROM trades")
    rows = await cursor.fetchall()

    if not rows:
        await update.message.reply_text("No trades yet ❌")
        return

    total = len(rows)
    wins = 0
    rr_total = 0
    pair_stats = {}

    for pair, rr, result in rows:
        if result.lower() == "win":
            wins += 1
            rr_total += rr
        else:
            rr_total -= 1  # assume risk = 1

        if pair not in pair_stats:
            pair_stats[pair] = {"wins": 0, "losses": 0, "rr": 0}

        if result.lower() == "win":
            pair_stats[pair]["wins"] += 1
            pair_stats[pair]["rr"] += rr
        else:
            pair_stats[pair]["losses"] += 1
            pair_stats[pair]["rr"] -= 1

    win_rate = (wins / total) * 100
    avg_rr = rr_total / total

    best_pair = max(pair_stats.items(), key=lambda x: x[1]["rr"])[0]
    worst_pair = min(pair_stats.items(), key=lambda x: x[1]["rr"])[0]
    most_traded = max(pair_stats.items(), key=lambda x: (x[1]["wins"] + x[1]["losses"]))[0]

    report_text = f"""
📊 TRADING REPORT

Total Trades: {total}
Win Rate: {win_rate:.2f}%
Average RR: {avg_rr:.2f}

🥇 Best Pair: {best_pair}
🔻 Worst Pair: {worst_pair}
📈 Most Traded: {most_traded}
"""

    await update.message.reply_text(report_text)

# ---------------- MAIN ----------------
async def on_startup(app):
    await init_db()

app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CommandHandler("report", report))

print("Bot running...")
app.run_polling()