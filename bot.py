import asyncio  # <- ekle

async def kasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Kasa verileri alınıyor...")
    try:
        users = load_users()
        devirs = load_devirs()
        results = []
        total = 0

        # -----------------------------
        # Tüm kullanıcılar için async görevler oluştur
        # -----------------------------
        tasks = []
        for label, info in users.items():
            tasks.append(fetch_user_amount(PANELS[info["panel"]], info["uuid"]))

        # -----------------------------
        # Hepsini paralel çalıştır
        # -----------------------------
        net_values = await asyncio.gather(*tasks, return_exceptions=True)

        # -----------------------------
        # Sonuçları işle
        # -----------------------------
        for i, label in enumerate(sorted(users.keys())):
            net = net_values[i]
            if isinstance(net, Exception):  # hata olursa 0 al
                net = 0
            devir = float(devirs.get(label, 0))
            net_total = net + devir
            total += net_total
            net_str = f"{int(net_total):,}".replace(",", ".") + " TL"
            results.append(f"{label} : {net_str}")

        # loading mesajını sil
        await msg.delete()

        # 5'li gruplar halinde gönder
        chunk_size = 5
        for i in range(0, len(results), chunk_size):
            chunk = results[i:i + chunk_size]
            await update.message.reply_text("\n".join(chunk))

        # toplam mesajı
        await update.message.reply_text(
            f"TOPLAM KASA : {int(total):,}".replace(",", ".") + " TL"
        )

    except Exception as e:
        await msg.edit_text(f"❌ Hata oluştu:\n{e}")
