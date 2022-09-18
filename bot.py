import csv
import logging
import os
import shutil
from zipfile import ZipFile

import aiofiles
import httpx
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


anki_csv_path = "anki.csv"
anki_speech_dir = "anki/"
anki_archive_path = "anki.zip"


async def start(update, context):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "Cheść👋 Mówisz po polsku? 🇵🇱\n"
            "Send me a word or phrase in polish and I'll help you!"
        ),
    )


async def say(update, context):
    text = update.message.text
    logger.info(text)

    # download an audio from Google Translate
    content = None
    async with httpx.AsyncClient() as client:
        translate_url = (
            "https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl=pl&q="
        )
        response = await client.get(f"{translate_url}{text}")
        content = response.content

    if not content:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Failed to generate the speech. Please try again.",
        )
        return

    # save the audio to /tmp dir
    speech_path = f"/tmp/{text}.mp3"
    async with aiofiles.open(speech_path, "wb") as f:
        await f.write(response.content)

    # send audio file to the user
    with open(speech_path, "rb") as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=f)

    # record anki cards
    if os.path.exists(anki_csv_path):
        with open(anki_csv_path, "a") as f:
            writer = csv.writer(f)
            writer.write([text, f"{text}<br>[sound:{text}.mp3]"])

        if not os.path.exists(anki_speech_dir):
            os.mkdir(anki_speech_dir)
        os.rename(speech_path, f"{anki_speech_dir}/{text}.mp3")
        return

    # clean up temporary audio
    os.remove(speech_path)


async def anki(update, context):
    # create the anki file
    if not os.path.exists(anki_csv_path):
        open(anki_csv_path, "w").close()
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "💾 Recording the data for Anki. "
                "Use the /anki command again to finish."
            ),
        )
        return

    with open(anki_csv_path, "rb") as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=f)

    with ZipFile(anki_archive_path, "w") as z:
        for dname, _, fnames in os.walk(anki_speech_dir):
            for fname in fnames:
                fpath = os.path.join(dname, fname)
                z.write(fpath, os.path.basename(fpath))

    with open(anki_archive_path, "rb") as f:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=f)

    os.remove(anki_csv_path)
    os.remove(anki_archive_path)
    shutil.rmtree(anki_speech_dir)


if __name__ == "__main__":
    application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

    start_handler = CommandHandler("start", start)
    say_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), say)
    anki_handler = CommandHandler("anki", anki)

    application.add_handler(start_handler)
    application.add_handler(say_handler)
    application.add_handler(anki_handler)

    application.run_polling()
