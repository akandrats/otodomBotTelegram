import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = "8358134069:AAFFaIcJLb_zT5pmJSo-l_LLTlReU3hoGAY"

# ===== PAMIĘĆ (bez bazy) =====
user_filters = {}
sent_links = set()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ===== KOMENDY =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Cześć! Podaj parametry w jednej wiadomości:\n\n"
        "miasto; cena_min; cena_max; metraż_min; metraż_max; pokoje\n\n"
        "📌 Przykład:\n"
        "warszawa; 600000; 800000; 50; 70; 3"
    )

async def set_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        city, pmin, pmax, amin, amax, rooms = update.message.text.split(";")
        chat_id = update.message.chat_id

        user_filters[chat_id] = {
            "city": city.strip(),
            "price_min": int(pmin),
            "price_max": int(pmax),
            "area_min": int(amin),
            "area_max": int(amax),
            "rooms": int(rooms),
        }

        await update.message.reply_text("✅ Filtry zapisane. Sprawdzam ogłoszenia co 10 minut.")
    except Exception:
        await update.message.reply_text("❌ Zły format danych.")

# ===== SCRAPING =====

def check_otodom():
    for chat_id, f in user_filters.items():
        url = (
            f"https://www.otodom.pl/pl/oferty/sprzedaz/mieszkanie/"
            f"{f['city']}?"
            f"priceMin={f['price_min']}&priceMax={f['price_max']}"
            f"&areaMin={f['area_min']}&areaMax={f['area_max']}"
            f"&roomsNumber={f['rooms']}"
        )

        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        offers = soup.select("article")

        for offer in offers:
            link_tag = offer.find("a", href=True)
            price_tag = offer.select_one("[data-testid='ad-price']")

            if not link_tag or not price_tag:
                continue

            link = "https://www.otodom.pl" + link_tag["href"]

            if link in sent_links:
                continue

            title = link_tag.get_text(strip=True)
            price = price_tag.get_text(strip=True)

            sent_links.add(link)

            app.bot.send_message(
                chat_id=chat_id,
                text=f"🏠 {title}\n💰 {price}\n🔗 {link}"
            )

def check_olx():
    for chat_id, f in user_filters.items():
        url = (
            f"https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/"
            f"{f['city']}/?"
            f"search[filter_float_price:from]={f['price_min']}"
            f"&search[filter_float_price:to]={f['price_max']}"
            f"&search[filter_float_m:from]={f['area_min']}"
            f"&search[filter_float_m:to]={f['area_max']}"
            f"&search[filter_enum_rooms]={f['rooms']}"
        )

        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        offers = soup.select("a[data-cy='listing-ad-title']")

        for offer in offers:
            link = offer["href"]

            if link in sent_links:
                continue

            title = offer.get_text(strip=True)
            sent_links.add(link)

            app.bot.send_message(
                chat_id=chat_id,
                text=f"🏠 {title}\n🔗 {link}\n(OLX)"
            )

# ===== START =====

def main():
    global app

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_filters))

    scheduler = BackgroundScheduler()
    scheduler.add_job(check_otodom, "interval", minutes=10)
    scheduler.add_job(check_olx, "interval", minutes=15)
    scheduler.start()

    print("🤖 Bot działa...")
    app.run_polling()


if __name__ == "__main__":
    main()
