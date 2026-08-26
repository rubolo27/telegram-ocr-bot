import os
import re
import numpy as np
import cv2
import pytesseract
from telegram import Update
from telegram.ext import Application, MessageHandler, filters

# Il token viene preso dalle variabili d'ambiente di Render
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

async def handle_photo(update: Update, context):
    # Scarica la foto
    photo = await update.message.photo[-1].get_file()
    img_bytes = await photo.download_as_bytearray()
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

    # Preprocessing semplice per migliorare OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # OCR
    text = pytesseract.image_to_string(thresh, lang="eng", config="--psm 6")

    # Estrai numeri tra 40 e 99 (tipici overall)
    numbers = [int(x) for x in re.findall(r"\b\d{2,3}\b", text) if 40 <= int(x) <= 99]

    if not numbers:
        await update.message.reply_text(
            "Non ho trovato numeri validi. Prova con uno screenshot più chiaro o più grande."
        )
        return

    avg = sum(numbers) / len(numbers)
    await update.message.reply_text(
        f"Overall trovati: {numbers}\nMedia overall: {avg:.1f}"
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    # Polling semplice, va bene su Render
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
