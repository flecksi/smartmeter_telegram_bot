import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from dotenv import load_dotenv
import os

import plotly.graph_objects as go

from smartmeter_utils import (
    get_sngraz,
    power_linechart_last_day,
    energy_barchart_over_days,
    power_linechart_last_day_with_history,
)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
SNGRAZ_EMAIL = os.getenv("SNGRAZ_EMAIL")
SNGRAZ_PASSWORD = os.getenv("SNGRAZ_PWD")
TIMEZONE = os.getenv("TIMEZONE")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def get_consumption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id == TELEGRAM_CHAT_ID:
        logging.info(f"get_consumption command received, {chat_id=}")

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"trying to connect to SNGraz...",
        )

        summaries = await get_sngraz(
            sngraz_email=SNGRAZ_EMAIL, sngraz_pwd=SNGRAZ_PASSWORD, timezone=TIMEZONE
        )

        for summary in summaries:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"installation id:{summary.installation_id}: {summary.number_of_days} days ({summary.first_date} to {summary.last_date})\n > {summary.norm_consumption_last_day_kWh_per_year:.0f}kWh/Year (last day)\n > {summary.norm_consumption_last_week_kWh_per_year:.0f}kWh/Year (last week)\n > {summary.norm_consumption_all_data_kWh_per_year:.0f}kWh/Year (last {summary.number_of_days} days)",
            )

            await context.bot.send_photo(
                chat_id=chat_id,
                # photo=power_linechart_last_day(summary).to_image(),
                photo=power_linechart_last_day_with_history(summary).to_image(),
            )

            await context.bot.send_photo(
                chat_id=chat_id,
                photo=energy_barchart_over_days(summary).to_image(),
            )

    else:
        logging.warning(f"Unauthorized chat_id={chat_id}")
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"WARNING: /get_consumption command from unauthorized chat (chat_id={chat_id})",
        )


# async def startup_msg(app: ApplicationBuilder):
#     return await app.bot.send_message(
#         chat_id=TELEGRAM_CHAT_ID,
#         text="bot started",
#     )


if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    get_consumption_handler = CommandHandler("get_consumption", get_consumption)

    application.add_handler(get_consumption_handler)

    # startup_msg(application)

    application.run_polling()
