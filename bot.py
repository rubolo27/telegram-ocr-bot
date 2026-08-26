import os
import re

import cv2
import numpy as np
import pytesseract

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    await update.message.reply_text(
        "Bot attivo!\n\n"
        "Mandami uno screenshot delle formazioni. "
        "Calcolerò separatamente la media overall della squadra a sinistra "
        "e della squadra a destra."
    )


def trova_overall(immagine) -> list[int]:
    """
    Legge gli overall da una porzione dell'immagine.
    Sono ammessi overall di 2 o 3 cifre, tra 40 e 150.
    """

    if immagine is None or immagine.size == 0:
        return []

    # Converti l'immagine in bianco e nero
    gray = cv2.cvtColor(immagine, cv2.COLOR_BGR2GRAY)

    # Ingrandisce i caratteri, utile per screenshot mobile
    gray = cv2.resize(
        gray,
        None,
        fx=4,
        fy=4,
        interpolation=cv2.INTER_CUBIC
    )

    # Aumenta contrasto locale
    clahe = cv2.createCLAHE(
        clipLimit=3.0,
        tileGridSize=(8, 8)
    )
    gray = clahe.apply(gray)

    # Trasforma in immagine bianca e nera
    _, threshold = cv2.threshold(
        gray,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # OCR: legge solo cifre
    config = "--psm 6 -c tessedit_char_whitelist=0123456789"

    testo = pytesseract.image_to_string(
        threshold,
        lang="eng",
        config=config
    )

    # Cerca numeri composti da 2 o 3 cifre
    numeri_trovati = re.findall(r"\b\d{2,3}\b", testo)

    overall = []

    for numero in numeri_trovati:
        valore = int(numero)

        # Accetta gli overall plausibili per il gioco.
        # Esclude numeri di maglia 1, 5, 17 ecc.
        if 40 <= valore <= 150:
            overall.append(valore)

    # Elimina eventuali duplicati consecutivi generati dall'OCR
    risultati = []

    for valore in overall:
        if not risultati or risultati[-1] != valore:
            risultati.append(valore)

    # Una squadra ha al massimo 11 giocatori
    return risultati[:11]


def calcola_media(numeri: list[int]) -> float | None:
    if not numeri:
        return None

    return sum(numeri) / len(numeri)


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
) -> None:
    try:
        await update.message.reply_text(
            "Sto analizzando le due formazioni..."
        )

        # Prende la versione più grande della foto ricevuta
        photo = update.message.photo[-1]

        telegram_file = await photo.get_file()
        image_bytes = await telegram_file.download_as_bytearray()

        image = cv2.imdecode(
            np.frombuffer(image_bytes, np.uint8),
            cv2.IMREAD_COLOR
        )

        if image is None:
            await update.message.reply_text(
                "Non riesco a leggere questa immagine. "
                "Prova a inviarla di nuovo come foto."
            )
            return

        altezza, larghezza = image.shape[:2]

        # Ritagli adattati al layout mostrato nello screenshot:
        #
        # - Sinistra: tabella rossa Sporting CP
        # - Destra: tabella azzurra Atalanta
        #
        # Il ritaglio include solo la fascia finale, dove si trovano
        # i valori overall, per evitare i numeri di maglia.
        #
        # Le percentuali funzionano anche con immagini di dimensioni diverse.
        left_overall_area = image[
            int(altezza * 0.23):int(altezza * 0.88),
            int(larghezza * 0.33):int(larghezza * 0.38)
        ]

        right_overall_area = image[
            int(altezza * 0.23):int(altezza * 0.88),
            int(larghezza * 0.83):int(larghezza * 0.88)
        ]

        overall_sinistra = trova_overall(left_overall_area)
        overall_destra = trova_overall(right_overall_area)

        media_sinistra = calcola_media(overall_sinistra)
        media_destra = calcola_media(overall_destra)

        if not overall_sinistra and not overall_destra:
            await update.message.reply_text(
                "Non sono riuscito a trovare gli overall.\n\n"
                "Invia uno screenshot nitido, con le due liste ben visibili. "
                "Meglio inviarlo come immagine e non come documento."
            )
            return

        messaggio = "RISULTATO OCR\n\n"

        if overall_sinistra:
            messaggio += (
                "SQUADRA SINISTRA\n"
                f"Overall trovati: {', '.join(map(str, overall_sinistra))}\n"
                f"Giocatori letti: {len(overall_sinistra)}/11\n"
                f"Media overall: {media_sinistra:.2f}\n"
            )
        else:
            messaggio += (
                "SQUADRA SINISTRA\n"
                "Nessun overall trovato.\n"
            )

        messaggio += "\n"

        if overall_destra:
            messaggio += (
                "SQUADRA DESTRA\n"
                f"Overall trovati: {', '.join(map(str, overall_destra))}\n"
                f"Giocatori letti: {len(overall_destra)}/11\n"
                f"Media overall: {media_destra:.2f}"
            )
        else:
            messaggio += (
                "SQUADRA DESTRA\n"
                "Nessun overall trovato."
            )

        await update.message.reply_text(messaggio)

    except Exception as errore:
        # Il dettaglio viene scritto nei log Railway
        print(f"Errore OCR completo: {repr(errore)}")

        await update.message.reply_text(
            "Si è verificato un errore durante la lettura dell'immagine.\n"
            "Controlla i log di Railway e cerca la riga: "
            "'Errore OCR completo'."
        )


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
