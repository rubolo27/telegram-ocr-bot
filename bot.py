import os
import re
import numpy as np
import cv2
import pytesseract

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    await update.message.reply_text(
        "Bot attivo! Mandami uno screenshot delle formazioni."
    )


def trova_overall(immagine):
    """
    Legge gli overall da una porzione dell'immagine.
    Gli overall validi sono compresi tra 100 e 150.
    """

    if immagine is None:
        return []

    gray = cv2.cvtColor(immagine, cv2.COLOR_BGR2GRAY)

    # Ingrandimento per aiutare l'OCR
    gray = cv2.resize(
        gray,
        None,
        fx=3,
        fy=3,
        interpolation=cv2.INTER_CUBIC
    )

    # Contrasto automatico
    gray = cv2.equalizeHist(gray)

    # Soglia binaria
    _, threshold = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # Cerca solo numeri di 3 cifre
    config = (
        "--psm 6 "
        "-c tessedit_char_whitelist=0123456789"
    )

    testo = pytesseract.image_to_string(
        threshold,
        config=config
    )

# Accetta numeri di 2 o 3 cifre
numeri = re.findall(r"\b\d{2,3}\b", testo)

risultati = []

for numero in numeri:
    valore = int(numero)

    # Accetta overall da 40 a 150.
    # Puoi cambiare questi limiti se nel gioco esistono valori diversi.
    if 40 <= valore <= 150:
        risultati.append(valore)

    return risultati


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:

    try:
        await update.message.reply_text(
            "Sto leggendo le due formazioni..."
        )

        # Scarica l'immagine ricevuta
        foto = update.message.photo[-1]
        file = await foto.get_file()
        immagine_bytes = await file.download_as_bytearray()

        immagine = cv2.imdecode(
            np.frombuffer(immagine_bytes, np.uint8),
            cv2.IMREAD_COLOR
        )

        if immagine is None:
            await update.message.reply_text(
                "Non riesco a leggere questa immagine."
            )
            return

        altezza, larghezza = immagine.shape[:2]

        # Ritaglia le zone delle due squadre.
        # Escludiamo titolo, pulsanti e parte centrale.
        sinistra = immagine[
            int(altezza * 0.20):int(altezza * 0.90),
            int(larghezza * 0.13):int(larghezza * 0.39)
        ]

        destra = immagine[
            int(altezza * 0.20):int(altezza * 0.90),
            int(larghezza * 0.61):int(larghezza * 0.87)
        ]

        overall_sinistra = trova_overall(sinistra)
        overall_destra = trova_overall(destra)

        # Teniamo al massimo 11 giocatori per squadra
        overall_sinistra = overall_sinistra[:11]
        overall_destra = overall_destra[:11]

        if not overall_sinistra and not overall_destra:
            await update.message.reply_text(
                "Non ho trovato gli overall.\n\n"
                "Controlla che lo screenshot sia nitido e che "
                "i numeri siano visibili."
            )
            return

        messaggio = ""

        if overall_sinistra:
            media_sinistra = sum(overall_sinistra) / len(overall_sinistra)

            messaggio += (
                "SQUADRA SINISTRA\n"
                f"Overall: {', '.join(map(str, overall_sinistra))}\n"
                f"Giocatori letti: {len(overall_sinistra)}\n"
                f"Media overall: {media_sinistra:.2f}\n"
            )
        else:
            messaggio += (
                "SQUADRA SINISTRA\n"
                "Nessun overall rilevato.\n"
            )

        messaggio += "\n"

        if overall_destra:
            media_destra = sum(overall_destra) / len(overall_destra)

            messaggio += (
                "SQUADRA DESTRA\n"
                f"Overall: {', '.join(map(str, overall_destra))}\n"
                f"Giocatori letti: {len(overall_destra)}\n"
                f"Media overall: {media_destra:.2f}\n"
            )
        else:
            messaggio += (
                "SQUADRA DESTRA\n"
                "Nessun overall rilevato.\n"
            )

        await update.message.reply_text(messaggio)

     except Exception as errore:
        print(f"Errore OCR completo: {repr(errore)}")

        await update.message.reply_text(
            "Errore durante la lettura dell'immagine.\n"
            "Controlla i log su Railway: serve il dettaglio dell'errore."
        )

        print(f"Errore OCR: {errore}")


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(
        CommandHandler("start", start_command)
    )

    app.add_handler(
        MessageHandler(filters.PHOTO, handle_photo)
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
