import os
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TOKEN = os.getenv("TELEGRAM_TOKEN")

# ===== PAMIĘĆ =====
user_filters = {}
sent_links = set()

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ===== KOMENDY =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Cześć! Podaj parametry w jednej wiadomości:\n\n"
        "województwo; miasto; cena_min; cena_max; metraż_min; metraż_max; pokoje (1,2); rok_budowy_min; słowo_w_opisie\n\n"
        "📌 Przykład:\n"
        "malopolskie; krakow; 400000; 650000; 25; 30; 1,2; 2000; garaz"
    )


async def set_filters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        parts = [p.strip() for p in update.message.text.split(";")]
        if len(parts) != 9:
            raise ValueError("Nieprawidłowa liczba parametrów (powinno być 9)")

        region, city, pmin, pmax, amin, amax, rooms_str, build_year_min, description = parts

        user_filters[chat_id] = {
            "region": region,
            "city": city,
            "price_min": int(pmin),
            "price_max": int(pmax),
            "area_min": int(amin),
            "area_max": int(amax),
            "rooms_label": [r.strip() for r in rooms_str.split(",")],
            "build_year_min": int(build_year_min),
            "description": description.replace(" ", "+"),
        }

        await update.message.reply_text("✅ Filtry zapisane. Sprawdzam ogłoszenia co jakiś czas.")
    except Exception as e:
        await update.message.reply_text(f"❌ Zły format lub błąd danych.\nBłąd: {str(e)}")


# ===== SCRAPING =====
# (pozostałe funkcje check_otodom i check_olx zostawiam bez zmian – tylko drobne poprawki bezpieczeństwa)
# ... (tu wklej swoje funkcje check_otodom i check_olx)


def main():
    # Najnowszy, zalecany sposób w v22.x
    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .get_updates_read_timeout(30)
        .get_updates_write_timeout(30)
        .get_updates_pool_timeout(30)
        .build()
    )

    # Dodajemy handler'y
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, set_filters))

    # JobQueue – teraz jest dostępne po instalacji z [job-queue]
    job_queue = application.job_queue

    if job_queue is None:
        print("!!! JobQueue nie jest dostępne. Zainstaluj python-telegram-bot z [job-queue] !!!")
        return

    # Uruchamiamy zadania cykliczne
    job_queue.run_repeating(
        callback=check_otodom,
        interval=600,   # 10 minut
        first=10
    )

    job_queue.run_repeating(
        callback=check_olx,
        interval=900,   # 15 minut
        first=30
    )

    print("🤖 Bot wystartował! Sprawdzanie co 10/15 minut.")
    
    # Start bota
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
    