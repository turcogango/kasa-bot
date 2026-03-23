import os
import ssl
import aiohttp
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ==============================
# RAILWAY ENV VARIABLES
# ==============================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PANEL1_URL = os.environ.get("PANEL1_URL")
PANEL1_USER = os.environ.get("PANEL1_USER")
PANEL1_PASS = os.environ.get("PANEL1_PASS")
PANEL2_URL = os.environ.get("PANEL2_URL")
PANEL2_USER = os.environ.get("PANEL2_USER")
PANEL2_PASS = os.environ.get("PANEL2_PASS")

# ==============================
# PANEL AYARLARI
# ==============================
PANELS = {
    "panel1": {"url": PANEL1_URL, "username": PANEL1_USER, "password": PANEL1_PASS},
    "panel2": {"url": PANEL2_URL, "username": PANEL2_USER, "password": PANEL2_PASS}
}

# ==============================
# USERS.JSON OKU
# ==============================
def load_users():
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# ==============================
# DEVİR OKU
# ==============================
def load_devirs():
    try:
        with open("devir.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# ==============================
# VERİ ÇEK
# ==============================
async def fetch_user_amount(panel_config, user_uuid):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_config['url']}/login"
    reports_url = f"{panel_config['url']}/reports/quickly"

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
        async with session.get(login_url) as r:
            text = await r.text()
            token = ""
            for line in text.splitlines():
                if 'name="_token"' in line:
                    token = line.split('value="')[1].split('"')[0]
                    break

        await session.post(login_url, data={
            "_token": token,
            "email": panel_config['username'],
            "password": panel_config['password']
        })

        async with session.get(reports_url) as r:
            text = await r.text()
            csrf = ""
            for line in text.splitlines():
                if 'csrf-token' in line:
                    csrf = line.split('content="')[1].split('"')[0]
                    break

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")

        async with session.post(
            reports_url,
            headers={"X-CSRF-TOKEN": csrf, "Content-Type": "application/json"},
            json={"site": "", "dateone": today, "datetwo": today, "bank": "", "user": user_uuid}
        ) as r:
            data = await r.json()
            deposit_total = float(data.get("deposit", [0])[0] or 0)
            withdraw_total = float(data.get("withdraw", [0])[0] or 0)
            delivery_total = float(data.get("delivery", [0, 0])[1] or 0)
            return deposit_total - withdraw_total - delivery_total

# ==============================
# /kasa KOMUTU
# ==============================
async def kasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Kasa verileri alınıyor...")
    try:
        users = load_users()
        devirs = load_devirs()
        results = []
        total = 0

        # Paralel görevler oluştur
        tasks = []
        user_labels = sorted(users.keys())
        for label in user_labels:
            info = users[label]
            tasks.append(fetch_user_amount(PANELS[info["panel"]], info["uuid"]))

        # Paralel çalıştır
        net_values = await asyncio.gather(*tasks, return_exceptions=True)

        # Sonuçları işleme
        for i, label in enumerate(user_labels):
            net = net_values[i]
            if isinstance(net, Exception):
                net = 0
            devir = float(devirs.get(label, 0))
            net_total = net + devir
            total += net_total
            net_str = f"{int(net_total):,}".replace(",", ".") + " TL"
            results.append(f"{label} : {net_str}")

        await msg.delete()  # loading mesajını sil

        # 5'erli gruplar halinde gönder
        chunk_size = 5
        for i in range(0, len(results), chunk_size):
            chunk = results[i:i + chunk_size]
            await update.message.reply_text("\n".join(chunk))

        # toplam mesaj
        await update.message.reply_text(
            f"TOPLAM KASA : {int(total):,}".replace(",", ".") + " TL"
        )

    except Exception as e:
        await msg.edit_text(f"❌ Hata oluştu:\n{e}")

# ==============================
# BOTU BAŞLAT
# ==============================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("kasa", kasa))
    print("Bot çalışıyor...")
    app.run_polling()
