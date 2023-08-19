import pandas as pd
from dataclasses import dataclass
import datetime
from sngraz import StromNetzGraz
import plotly.graph_objects as go
import plotly.express as px


@dataclass
class PowerConsumptionSummary:
    df: pd.DataFrame
    first_date: datetime.datetime
    last_date: datetime.datetime
    number_of_days: int
    total_consumption_last_day_kWh: float
    total_consumption_last_week_kWh: float
    total_consumption_all_data_kWh: float
    norm_consumption_last_day_kWh_per_year: float
    norm_consumption_last_week_kWh_per_year: float
    norm_consumption_all_data_kWh_per_year: float
    min_power_last_day_W: float
    max_power_last_day_W: float
    installation_id: str = None
    installation_address: str = None
    meter_id: str = None
    meter_shortname: str = None


def get_summary(df: pd.DataFrame) -> PowerConsumptionSummary:
    last_date = df.date[-1]
    first_date = df.date[0]
    number_of_days = (last_date - first_date).days
    df_last_day = df[df.date == last_date]
    total_consumption_last_day_kWh = df_last_day.e_delta_kWh.sum()
    min_power_last_day_W = df_last_day.power_W.min()
    max_power_last_day_W = df_last_day.power_W.max()
    df_last_week = df[df.date >= last_date - datetime.timedelta(days=7)]
    total_consumption_last_week_kWh = df_last_week.e_delta_kWh.sum()
    total_consumption_all_data_kWh = df.e_delta_kWh.sum()

    return PowerConsumptionSummary(
        df=df,
        first_date=first_date,
        last_date=last_date,
        number_of_days=number_of_days,
        total_consumption_last_day_kWh=total_consumption_last_day_kWh,
        total_consumption_last_week_kWh=total_consumption_last_week_kWh,
        total_consumption_all_data_kWh=total_consumption_all_data_kWh,
        min_power_last_day_W=min_power_last_day_W,
        max_power_last_day_W=max_power_last_day_W,
        norm_consumption_last_day_kWh_per_year=total_consumption_last_day_kWh * 365,
        norm_consumption_last_week_kWh_per_year=total_consumption_last_week_kWh
        / 7
        * 365,
        norm_consumption_all_data_kWh_per_year=total_consumption_all_data_kWh
        / number_of_days
        * 365,
    )


async def get_sngraz(
    sngraz_email: str, sngraz_pwd: str, timezone: str
) -> list[PowerConsumptionSummary]:
    sn = StromNetzGraz(sngraz_email, sngraz_pwd)
    await sn.authenticate()
    await sn.update_info()

    summaries = []
    for installation in sn.get_installations():
        installation_id = installation._installation_id
        installation_address = installation._address
        for meter in installation.get_meters():
            meter_id = meter.id
            meter_shortname = meter._short_name

            await meter.fetch_consumption_data()

            energy_data = [
                (i["readTime"], i["MR"], i["readingValues"][0]["readingState"])
                for i in meter._data
            ]
            df = pd.DataFrame(
                energy_data, columns=["time", "consump_kWh", "readingState"]
            )
            df.drop(df.tail(1).index, inplace=True)
            df.set_index("time", inplace=True)
            df.index = df.index.tz_convert(timezone)
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
            summary.installation_id = installation_id
            summary.installation_address = installation_address
            summary.meter_id = meter_id
            summary.meter_shortname = meter_shortname

            summaries.append(summary)

    await sn.close_connection()

    return summaries


def power_linechart_last_day(
    summary: PowerConsumptionSummary, width: int = 1000
) -> go.Figure:
    df_last_day = summary.df[summary.df.date == summary.last_date]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_last_day.index,
            y=df_last_day.power_W,
            mode="lines+markers",
            name="power",
            line=dict(color="blue"),
        )
    )
    fig.update_layout(
        title=f"Last day's power consumption <br> {summary.installation_id} ({summary.installation_address})",
        # xaxis_title="time",
        yaxis_title="Power [W]",
        width=width,
    )
    return fig


def energy_barchart_over_days(
    summary: PowerConsumptionSummary, width: int = 1000
) -> go.Figure:
    fig = go.Figure()
    df_daily_energy = summary.df.groupby("date").e_delta_kWh.sum()
    fig.add_trace(
        go.Bar(
            x=df_daily_energy.index,
            y=df_daily_energy,
            name="energy",
            marker_color="blue",
        )
    )
    fig.update_layout(
        title=f"Daily energy consumption <br> {summary.installation_id} ({summary.installation_address})",
        yaxis_title="Energy [kWh]",
        width=width,
    )
    # # make the last week's bars blue, the day's bar green and the rest grey
    # bar_colors = ["grey"] * len(fig.data[0].x)
    # bar_colors[-7:] = ["blue"] * 7
    # bar_colors[-1] = "green"

    # make weekend bars grey, weekday bars blue
    bar_colors = ["grey"] * len(fig.data[0].x)
    for i, date in enumerate(fig.data[0].x):
        if date.weekday() >= 5:
            bar_colors[i] = "grey"
        else:
            bar_colors[i] = "blue"

    fig.data[0].marker.color = bar_colors

    return fig


def power_linechart_last_day_with_history(
    summary: PowerConsumptionSummary,
    width: int = 1000,
) -> go.Figure:
    df_pivot_per_day = summary.df.pivot(
        index="date", columns="time_of_day", values="power_W"
    ).T

    fig = px.line(df_pivot_per_day)

    # make all but the last days lines grey and thin, and the last day's line blue and thick
    for i in range(len(fig.data) - 1):
        fig.data[i].line.color = "grey"
        fig.data[i].line.width = 1
    fig.data[-1].line.color = "blue"
    fig.data[-1].line.width = 4

    fig.update_layout(
        title=f"Power consumption over day (with history)<br> {summary.installation_id} ({summary.installation_address})",
        xaxis_title="time of day",
        yaxis_title="Power [W]",
        showlegend=False,
        width=width,
    )
    return fig
