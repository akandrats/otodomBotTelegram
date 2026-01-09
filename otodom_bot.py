import os
import asyncio
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
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv("TELEGRAM_TOKEN")

# ===== PAMIĘĆ =====
user_filters = {}
sent_links = set()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# ===== KOMENDY =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Cześć! Podaj parametry w jednej wiadomości (oddzielone średnikiem):\n\n"
        "województwo; miasto; cena_min; cena_max; metraż_min; metraż_max; pokoje (1,2); rok_budowy_min; słowo_w_opisie\n\n"
        "📌 Przykład:\n"
        "malopolskie; krakow; 400000; 650000; 25; 30; 1,2; 2000; garaz"
    )

async def set_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        (
            region, city, pmin, pmax, amin, amax, rooms_str,
            build_year_min, description
        ) = update.message.text.split(";")

        user_filters[chat_id] = {
            "region": region.strip(),
            "city": city.strip(),
            "price_min": int(pmin),
            "price_max": int(pmax),
            "area_min": int(amin),
            "area_max": int(amax),
            "rooms_label": [r.strip().upper() for r in rooms_str.split(",")],  # ONE,TWO
            "build_year_min": int(build_year_min),
            "description": description.strip().replace(" ", "+")
        }

        await update.message.reply_text("✅ Filtry zapisane. Sprawdzam ogłoszenia co 10 minut.")
    except Exception:
        await update.message.reply_text(
            "❌ Zły format danych. Użyj:\n"
            "województwo; miasto; cena_min; cena_max; metraż_min; metraż_max; pokoje (1,2); rok_budowy_min; słowo_w_opisie"
        )

# ===== SCRAPING =====
async def check_otodom():
    for chat_id, f in user_filters.items():
        rooms_params = ",".join(["ONE" if r=="1" else "TWO" for r in f["rooms_label"]])
        url = (
            f"https://www.otodom.pl/pl/wyniki/sprzedaz/mieszkanie/"
            f"{f['region']}/{f['city']}/?"
            f"limit=36"
            f"&priceMin={f['price_min']}&priceMax={f['price_max']}"
            f"&areaMin={f['area_min']}&areaMax={f['area_max']}"
            f"&roomsNumber={rooms_params}"
            f"&buildYearMin={f['build_year_min']}"
            f"&description={f['description']}"
            f"&by=DEFAULT&direction=DESC"
        )

        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            offers = soup.select("article")

            for offer in offers:
                link_tag = offer.find("a", href=True)
                price_tag = offer.select_one("[data-testid='ad-price']")
                desc_tag = offer.select_one("p[data-testid='ad-description']") or ""

                if not link_tag or not price_tag:
                    continue

                link = "https://www.otodom.pl" + link_tag["href"]
                if link in sent_links:
                    continue

                # dodatkowa walidacja słowa w opisie
                if f["description"].replace("+", " ").lower() not in desc_tag.get_text(strip=True).lower():
                    continue

                title = link_tag.get_text(strip=True)
                price = price_tag.get_text(strip=True)
                sent_links.add(link)

                await app.bot.send_message(
                    chat_id=chat_id,
                    text=f"🏠 {title}\n💰 {price}\n🔗 {link}\n(Otodom)"
                )
        except Exception as e:
            print(f"Otodom error: {e}")

async def check_olx():
    for chat_id, f in user_filters.items():
        rooms_params = ",".join(f["rooms_label"])
        url = (
            f"https://www.olx.pl/nieruchomosci/mieszkania/sprzedaz/"
            f"{f['city']}/?"
            f"search[filter_float_price:from]={f['price_min']}"
            f"&search[filter_float_price:to]={f['price_max']}"
            f"&search[filter_float_m:from]={f['area_min']}"
            f"&search[filter_float_m:to]={f['area_max']}"
            f"&search[filter_enum_rooms]={rooms_params}"
        )

        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(r.text, "html.parser")
            offers = soup.select("a[data-cy='listing-ad-title']")

            for offer in offers:
                link = offer["href"]
                if link in sent_links:
                    continue

                title = offer.get_text(strip=True)
                sent_links.add(link)

                await app.bot.send_message(
                    chat_id=chat_id,
                    text=f"🏠 {title}\n🔗 {link}\n(OLX)"
                )
        except Exception as e:
            print(f"OLX error: {e}")

# ===== START =====
async def main():
    global app
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_filters))

    # Scheduler działa w asyncio
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: asyncio.create_task(check_otodom()), "interval", minutes=10)
    scheduler.add_job(lambda: asyncio.create_task(check_olx()), "interval", minutes=15)
    scheduler.start()

    print("🤖 Bot działa...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
