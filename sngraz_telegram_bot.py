import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from dotenv import load_dotenv
import os
from sngraz import StromNetzGraz
import pandas as pd
import numpy as np
from dataclasses import dataclass
import datetime

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
SNGRAZ_EMAIL = os.getenv("SNGRAZ_EMAIL")
SNGRAZ_PASSWORD = os.getenv("SNGRAZ_PWD")
TIMEZONE = os.getenv("TIMEZONE")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


@dataclass
class PowerConsumptionSummary:
    first_date: datetime.datetime
    last_date: datetime.datetime
    number_of_days: int
    total_consumption_kWh: float
    average_consumption_last_day_kWh: float
    average_consumption_last_week_kWh: float
    average_consumption_all_data_kWh: float
    norm_consumption_last_day_kWh_per_year: float
    norm_consumption_last_week_kWh_per_year: float
    norm_consumption_all_data_kWh_per_year: float
    min_power_last_day_W: float
    max_power_last_day_W: float


def get_summary(df: pd.DataFrame) -> PowerConsumptionSummary:
    last_date = df.date[-1]
    first_date = df.date[0]
    number_of_days = (last_date - first_date).days
    total_consumption_kWh = df.e_delta_kWh.sum()
    df_last_day = df[df.date == last_date]
    average_consumption_last_day_kWh = df_last_day.e_delta_kWh.sum()
    min_power_last_day_W = df_last_day.power_W.min()
    max_power_last_day_W = df_last_day.power_W.max()
    df_last_week = df[df.date >= last_date - datetime.timedelta(days=7)]
    average_consumption_last_week_kWh = df_last_week.e_delta_kWh.sum()
    average_consumption_all_data_kWh = df.e_delta_kWh.sum()

    return PowerConsumptionSummary(
        first_date=first_date,
        last_date=last_date,
        number_of_days=number_of_days,
        total_consumption_kWh=total_consumption_kWh,
        average_consumption_last_day_kWh=average_consumption_last_day_kWh,
        average_consumption_last_week_kWh=average_consumption_last_week_kWh,
        average_consumption_all_data_kWh=average_consumption_all_data_kWh,
        min_power_last_day_W=min_power_last_day_W,
        max_power_last_day_W=max_power_last_day_W,
        norm_consumption_last_day_kWh_per_year=average_consumption_last_day_kWh * 365,
        norm_consumption_last_week_kWh_per_year=average_consumption_last_week_kWh
        / 7
        * 365,
        norm_consumption_all_data_kWh_per_year=average_consumption_all_data_kWh
        / number_of_days
        * 365,
    )


async def get_consumption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id == TELEGRAM_CHAT_ID:
        logging.info(f"get_consumption command received, {chat_id=} {type(chat_id)=}")

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"trying to connect to SNGraz...",
        )

        sn = StromNetzGraz(SNGRAZ_EMAIL, SNGRAZ_PASSWORD)
        await sn.authenticate()
        await sn.update_info()

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"authenticated at SNGraz, getting data...",
        )

        for installation in sn.get_installations():
            installation_id = installation._installation_id
            installation_address = installation._address
            for meter in installation.get_meters():
                meter_id = meter.id
                meter_shortname = meter._short_name
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"installation_id={installation_id} ({installation_address}), meter_id={meter_id} ({meter_shortname}). fetching data...",
                )
                await meter.fetch_consumption_data()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"fetched data, processing...",
                )
                energy_data = [
                    (i["readTime"], i["MR"], i["readingValues"][0]["readingState"])
                    for i in meter._data
                ]
                df = pd.DataFrame(
                    energy_data, columns=["time", "consump_kWh", "readingState"]
                )
                df.drop(df.tail(1).index, inplace=True)
                df.set_index("time", inplace=True)
                df.index = df.index.tz_convert(TIMEZONE)
                df["e_delta_kWh"] = df["consump_kWh"].diff()
                df["time_delta"] = df.index.to_series().diff().dt.total_seconds()
                df.dropna(inplace=True)
                df["power_W"] = 3600 * 1000.0 * df.e_delta_kWh / df.time_delta
                df["hour"] = df.index.hour
                df["day_of_year"] = df.index.dayofyear
                df["day_of_week"] = df.index.dayofweek
                df["day_of_month"] = df.index.day
                df["day_name"] = df.index.day_name()
                df["date"] = df.index.date
                df["time_of_day"] = df.index.time
                df["week"] = df.index.isocalendar().week
                df["month"] = df.index.month
                df["month_name"] = df.index.month_name()

                summary = get_summary(df)

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"processing done: {summary.number_of_days} days ({summary.first_date} to {summary.last_date})\n > {summary.norm_consumption_last_day_kWh_per_year:.0f}kWh/Year (yesterday)\n > {summary.norm_consumption_last_week_kWh_per_year:.0f}kWh/Year (last week)\n > {summary.norm_consumption_all_data_kWh_per_year:.0f}kWh/Year (last {summary.number_of_days} days)",
                )

        await sn.close_connection()
    else:
        logging.warning(f"Unauthorized chat_id={chat_id}")
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"WARNING: /get_consumption command from unauthorized chat (chat_id={chat_id})",
        )


if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    get_consumption_handler = CommandHandler("get_consumption", get_consumption)

    application.add_handler(get_consumption_handler)

    application.run_polling()
