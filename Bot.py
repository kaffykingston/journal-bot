import os
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes
)
import sqlite3

TOKEN = os.environ.get("BOT_TOKEN")

# ---------------- DATABASE SETUP ----------------
conn = sqlite3.connect("trades.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair TEXT,
    rr REAL,
    result TEXT,
    emotion TEXT,
    raw_text TEXT
)
""")
conn.commit()

# ---------------- MESSAGE HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    try:
        lines = text.split("\n")

        data = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip().lower()] = value.strip()

        pair = data.get("pair", "unknown")
        risk = data.get("risk", "0%")
        rr_raw = data.get("rr", "0:1")
        result = data.get("result", "unknown")
        emotion = data.get("emotion", "unknown")
        notes = data.get("notes", "")

        # convert RR "1:5" → 5
        try:
            rr = float(rr_raw.split(":")[1])
        except:
            rr = 0

        cursor.execute("""
        INSERT INTO trades (pair, rr, result, emotion, raw_text)
        VALUES (?, ?, ?, ?, ?)
        """, (pair, rr, result, emotion, text))

        conn.commit()

        await update.message.reply_text("Trade saved ✅")

    except Exception as e:
        await update.message.reply_text(
            "Format error ❌\nUse:\nPair: GBPJPY\nRR: 1:5\nResult: Win"
        )
async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT pair, rr, result FROM trades")
    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("No trades yet ❌")
        return

    total = len(rows)
    wins = 0
    rr_total = 0

    pair_stats = {}

    for pair, rr, result in rows:
        rr_total += rr

        if result.lower() == "win":
            wins += 1

        if pair not in pair_stats:
            pair_stats[pair] = {"wins": 0, "losses": 0, "rr": 0}

        if result.lower() == "win":
            pair_stats[pair]["wins"] += 1
        else:
            pair_stats[pair]["losses"] += 1

        pair_stats[pair]["rr"] += rr if result.lower() == "win" else -rr

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

# ---------------- BOT START ----------------
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CommandHandler("report", report))

print("Bot running...")
app.run_polling()
