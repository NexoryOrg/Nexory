import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from discord import app_commands
import calendar
from typing import Literal
from datetime import date
import io

class TaskCalendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="calendar", description="Generates a calendar with tasks for the specified month and year.")
    @app_commands.describe(
        scope="Choose whether to show tasks for the entire guild or just your own tasks.",
        month="The month for which to generate the calendar (1-12). Defaults to the current month.",
        year="The year for which to generate the calendar. Defaults to the current year."
    )
    async def kalender(self, interaction: discord.Interaction, scope: Literal["guild", "user"] = "user", month: int = None, year: int = None):
        today = date.today()
        month = month or today.month
        year = year or today.year

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT mode FROM nexory_guild_config WHERE guildID=%s",
                    (interaction.guild.id,)
                )
                config = await cur.fetchone()

        mode = config[0] if config else "light"

        if mode == "dark":
            bg_color = (28, 28, 30)
            card_color = (44, 44, 46)
            text_color = (240, 240, 245)
            subtext_color = (160, 160, 170)
        else:
            bg_color = (242, 242, 247)
            card_color = (255, 255, 255)
            text_color = (20, 20, 25)
            subtext_color = (120, 120, 130)

        ios_red = (255, 59, 48)
        ios_blue = (0, 122, 255)

        if scope.lower() == "guild":
            query = "SELECT title, date, remindme FROM nexory_guild_tasks WHERE date BETWEEN %s AND %s AND guildID=%s"
            params = (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]), interaction.guild.id)
        else:
            query = "SELECT title, date, remindme FROM nexory_user_tasks WHERE date BETWEEN %s AND %s AND userID=%s"
            params = (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]), interaction.user.id)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()

        tasks_by_day = {}
        for title, task_date, remindme in rows:
            tasks_by_day.setdefault(task_date.day, []).append((title, remindme))

        scale = 2
        width, height = 1600 * scale, 1100 * scale
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("arial.ttf", 70 * scale)
            font_weekday = ImageFont.truetype("arial.ttf", 30 * scale)
            font_day = ImageFont.truetype("arial.ttf", 34 * scale)
            font_event = ImageFont.truetype("arial.ttf", 22 * scale)
        except:
            font_title = ImageFont.load_default()
            font_weekday = ImageFont.load_default()
            font_day = ImageFont.load_default()
            font_event = ImageFont.load_default()

        draw.text(
            (width // 2, 80 * scale),
            f"{calendar.month_name[month]} {year}",
            fill=text_color,
            font=font_title,
            anchor="mm"
        )

        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(year, month)

        cell_width = width // 7
        cell_height = (height - 220 * scale) // len(month_days)
        start_y = 160 * scale

        weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        for i, name in enumerate(weekdays):
            x = i * cell_width + cell_width // 2
            color = ios_red if i >= 5 else subtext_color
            draw.text((x, start_y - 35 * scale), name, fill=color, font=font_weekday, anchor="mm")

        for row_idx, week in enumerate(month_days):
            for col_idx, day in enumerate(week):
                x1 = col_idx * cell_width + 10 * scale
                y1 = start_y + row_idx * cell_height + 10 * scale
                x2 = x1 + cell_width - 20 * scale
                y2 = y1 + cell_height - 20 * scale

                draw.rounded_rectangle(
                    [x1, y1, x2, y2],
                    radius=25 * scale,
                    fill=card_color
                )

                if day == 0:
                    continue

                day_x = x1 + 35 * scale
                day_y = y1 + 35 * scale

                if day == today.day and month == today.month and year == today.year:
                    r = 22 * scale
                    draw.ellipse(
                        (day_x - r, day_y - r, day_x + r, day_y + r),
                        fill=ios_red
                    )
                    draw.text((day_x, day_y), str(day), fill="white", font=font_day, anchor="mm")
                else:
                    color = ios_red if col_idx >= 5 else text_color
                    draw.text((day_x, day_y), str(day), fill=color, font=font_day, anchor="mm")

                if day in tasks_by_day:
                    events = tasks_by_day[day]
                    max_show = 1

                    for i, (title, remindme) in enumerate(events[:max_show]):
                        pill_color = ios_red if remindme else ios_blue
                        pill_y = y1 + 70 * scale + i * 35 * scale

                        draw.rounded_rectangle(
                            (x1 + 25 * scale, pill_y, x2 - 25 * scale, pill_y + 28 * scale),
                            radius=14 * scale,
                            fill=pill_color
                        )

                        draw.text(
                            (x1 + 40 * scale, pill_y + 14 * scale),
                            title[:18],
                            fill="white",
                            font=font_event,
                            anchor="lm"
                        )

                    if len(events) > max_show:
                        more_text = f"+{len(events)-max_show} weitere"
                        draw.text(
                            (x1 + 35 * scale, y1 + 75 * scale + max_show * 35 * scale),
                            more_text,
                            fill=subtext_color,
                            font=font_event,
                            anchor="lm"
                        )

        final_img = img.resize((1600, 1100), Image.LANCZOS)

        with io.BytesIO() as image_binary:
            final_img.save(image_binary, "PNG", optimize=True)
            image_binary.seek(0)

            file = discord.File(fp=image_binary, filename="calendar.png")
            await interaction.response.send_message(
                file=file,
                content=f"📅 **{scope.title()} Calendar** – {calendar.month_name[month]} {year}\nUser: {interaction.user.mention}",
            )

async def setup(bot):
    await bot.add_cog(TaskCalendar(bot))