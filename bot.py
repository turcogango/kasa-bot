import ssl
import aiohttp
import asyncio
import json
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")

PANELS = {
    "panel1": {
        "url": os.environ.get("PANEL1_URL"),
        "username": os.environ.get("PANEL1_USER"),
        "password": os.environ.get("PANEL1_PASS")
    },
    "panel2": {
        "url": os.environ.get("PANEL2_URL"),
        "username": os.environ.get("PANEL2_USER"),
        "password": os.environ.get("PANEL2_PASS")
    }
}

# ==============================
# JSON OKUMA
# ==============================
def load_users():
    with open("users.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_devirs():
    try:
        with open("devir.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

# ==============================
# PANEL LOGIN (TEK SEFER)
# ==============================
async def panel_login(session, panel):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel['url']}/login"

    async with session.get(login_url, ssl=ssl_ctx) as r:
        text = await r.text()

    token = text.split('name="_token" value="')[1].split('"')[0]

    await session.post(login_url, data={
        "_token": token,
        "email": panel['username'],
        "password": panel['password']
    }, ssl=ssl_ctx)

    return True

# ==============================
# VERİ ÇEKME
# ==============================
async def fetch_user(session, panel, uuid, sem):
    async with sem:
        try:
            today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
            url = f"{panel['url']}/reports/quickly"

            async with session.get(url) as r:
                text = await r.text()

            csrf = text.split('content="')[1].split('"')[0]

            async with session.post(
                url,
                headers={"X-CSRF-TOKEN": csrf, "Content-Type": "application/json"},
                json={
                    "site": "",
                    "dateone": today,
                    "datetwo": today,
                    "bank": "",
                    "user": uuid
                }
            ) as r:
                data = await r.json()

            deposit = float(data.get("deposit", [0])[0] or 0)
            withdraw = float(data.get("withdraw", [0])[0] or 0)
            delivery = float(data.get("delivery", [0, 0])[1] or 0)

            return deposit - withdraw - delivery

        except:
            return 0

# ==============================
# KASA KOMUTU
# ==============================
async def kasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Hesaplanıyor...")

    users = load_users()
    devirs = load_devirs()

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(connector=connector) as session:

        # PANEL LOGIN
        for panel in PANELS.values():
            await panel_login(session, panel)

        sem = asyncio.Semaphore(10)

        # ✅ SAYISAL SIRALAMA (DÜZELTME BURADA)
        labels = sorted(users.keys(), key=lambda x: int(re.search(r"\d+", x).group()))

        tasks = []
        for label in labels:
            info = users[label]
            panel = PANELS[info["panel"]]
            uuid = info["uuid"]
            tasks.append(fetch_user(session, panel, uuid, sem))

        nets = await asyncio.gather(*tasks)

        total = 0
        results = []

        for i, label in enumerate(labels):
            net = nets[i]
            devir = float(devirs.get(label, 0))

            net_total = net + devir
            total += net_total

            net_str = f"{int(net_total):,}".replace(",", ".") + " TL"
            results.append(f"{label} : {net_str}")

        results.append(f"\nTOPLAM: {int(total):,}".replace(",", ".") + " TL")

        await msg.edit_text("\n".join(results))

# ==============================
# BOT
# ==============================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("kasa", kasa))
    print("Bot çalışıyor...")
    app.run_polling()
