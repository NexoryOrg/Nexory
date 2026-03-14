import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from discord import app_commands
import calendar
from typing import Literal
from datetime import date
import io


class CalendarView(discord.ui.View):
    def __init__(self, cog, scope, month, year, day, user_id):
        super().__init__(timeout=300)
        self.cog = cog
        self.scope = scope
        self.month = month
        self.year = year
        self.day = day
        self.user_id = user_id
        self.message = None

    async def update_calendar(self, interaction: discord.Interaction):
        file = await self.cog.generate_calendar_image(
            interaction, self.scope, self.month, self.year, self.day
        )

        if self.message is None:
            await interaction.response.send_message(file=file, view=self)
            self.message = await interaction.original_response()
        else:
            await interaction.response.edit_message(attachments=[file], view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "You cannot control this calendar.", ephemeral=True
            )

        if self.day:
            self.day -= 1
            if self.day < 1:
                self.month -= 1
                if self.month < 1:
                    self.month = 12
                    self.year -= 1
                self.day = calendar.monthrange(self.year, self.month)[1]
        else:
            self.month -= 1
            if self.month < 1:
                self.month = 12
                self.year -= 1

        await self.update_calendar(interaction)

    @discord.ui.button(label="today", style=discord.ButtonStyle.primary)
    async def today(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "You cannot control this calendar.", ephemeral=True
            )

        today = date.today()
        self.year = today.year
        self.month = today.month
        self.day = None

        await self.update_calendar(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def forward(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "You cannot control this calendar.", ephemeral=True
            )

        if self.day:
            self.day += 1
            last_day = calendar.monthrange(self.year, self.month)[1]
            if self.day > last_day:
                self.day = 1
                self.month += 1
                if self.month > 12:
                    self.month = 1
                    self.year += 1
        else:
            self.month += 1
            if self.month > 12:
                self.month = 1
                self.year += 1

        await self.update_calendar(interaction)


class TaskCalendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="calendar",
        description="Generates a calendar with tasks for the specified month, year, or a specific day."
    )
    @app_commands.describe(
        scope="Choose whether to show tasks for the entire guild or just your own tasks.",
        month="The month for which to generate the calendar (1-12). Defaults to the current month.",
        year="The year for which to generate the calendar. Defaults to the current year.",
        day="Optional: specify a day to get a detailed task overview for that day."
    )
    async def calendar(
        self, 
        interaction: discord.Interaction, 
        scope: Literal["guild", "user"] = "user",
        month: int = None,
        year: int = None,
        day: int = None
    ):
        today = date.today()
        month = month or today.month
        year = year or today.year

        view = CalendarView(self, scope, month, year, day, interaction.user.id)
        await view.update_calendar(interaction)

    async def generate_calendar_image(self, interaction, scope, month, year, day):
        today = date.today()
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if scope.lower() == "guild":
                    await cur.execute(
                        "SELECT mode FROM nexory_guild_config WHERE guildID=%s",
                        (interaction.guild.id,)
                    )
                    config = await cur.fetchone()
                else:
                    await cur.execute(
                        "SELECT mode FROM nexory_user_config WHERE userID=%s",
                        (interaction.user.id,)
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
            query = "SELECT title, des, date, remindme FROM nexory_guild_tasks WHERE date BETWEEN %s AND %s AND guildID=%s"
            params = (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]), interaction.guild.id)
        else:
            query = "SELECT title, des, date, remindme FROM nexory_user_tasks WHERE date BETWEEN %s AND %s AND userID=%s"
            params = (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]), interaction.user.id)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()

        tasks_by_day = {}
        for title, des, task_date, remindme in rows:
            tasks_by_day.setdefault(task_date.day, []).append((title, des, remindme))

        scale = 2
        width, height = 1600 * scale, 1100 * scale
        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        try:
            font_title = ImageFont.truetype("arial.ttf", 70 * scale)
            font_subtitle = ImageFont.truetype("arial.ttf", 50 * scale)
            font_weekday = ImageFont.truetype("arial.ttf", 30 * scale)
            font_day = ImageFont.truetype("arial.ttf", 34 * scale)
            font_task_title = ImageFont.truetype("arial.ttf", 32 * scale)
            font_task_desc = ImageFont.truetype("arial.ttf", 24 * scale)
            font_event = ImageFont.truetype("arial.ttf", 22 * scale)
        except:
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()
            font_weekday = ImageFont.load_default()
            font_day = ImageFont.load_default()
            font_task_title = ImageFont.load_default()
            font_task_desc = ImageFont.load_default()
            font_event = ImageFont.load_default()

        if day:
            draw.text(
                (width // 2, 80 * scale),
                f"{calendar.day_name[date(year, month, day).weekday()]}, {month}.{day}.{year}",
                fill=text_color,
                font=font_title,
                anchor="mm"
            )
            draw.text(
                (width // 2, 150 * scale),
                f"{interaction.guild.name if scope.lower() == 'guild' else interaction.user.name}`s Tasks",
                fill=text_color,
                font=font_subtitle,
                anchor="mm"
            )
            y_offset = 200 * scale
            task_spacing = 100 * scale

            if day in tasks_by_day:
                for i, (title, description, remindme) in enumerate(tasks_by_day[day]):
                    pill_color = ios_red if remindme else ios_blue
                    pill_height = 80 * scale
                    pill_width = width - 2 * 100 * scale

                    draw.rounded_rectangle(
                        (100*scale, y_offset + i*task_spacing, 100*scale + pill_width, y_offset + i*task_spacing + pill_height),
                        radius=20*scale,
                        fill=pill_color
                    )

                    draw.text(
                        (120*scale, y_offset + i*task_spacing + 15*scale),
                        title,
                        fill="white",
                        font=font_task_title,
                        anchor="lm"
                    )

                    draw.text(
                        (120*scale, y_offset + i*task_spacing + 45*scale),
                        description if description else "-",
                        fill="white",
                        font=font_task_desc,
                        anchor="lm"
                    )

                    if remindme:
                        try:
                            bell_img = Image.open("database/images/belt.png").convert("RGBA")
                            bell_size = 28 * scale
                            bell_img = bell_img.resize((bell_size, bell_size))
                            bell_x = 100*scale + pill_width - 40*scale
                            bell_y = y_offset + i*task_spacing + pill_height / 2
                            img.paste(bell_img, (int(bell_x - bell_size/2), int(bell_y - bell_size/2)), bell_img)
                        except Exception as e:
                            print("Failed to load bell image:", e)

            else:
                draw.text(
                    (width//2, height//2),
                    "No tasks for this day.",
                    fill=subtext_color,
                    font=font_weekday,
                    anchor="mm"
                )

        else:
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
            weekdays = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

            for i, name in enumerate(weekdays):
                x = i * cell_width + cell_width // 2
                color = ios_red if i >= 5 else subtext_color
                draw.text((x, start_y - 35 * scale), name, fill=color, font=font_weekday, anchor="mm")

            for row_idx, week in enumerate(month_days):
                for col_idx, day_cell in enumerate(week):
                    x1 = col_idx * cell_width + 10 * scale
                    y1 = start_y + row_idx * cell_height + 10 * scale
                    x2 = x1 + cell_width - 20 * scale
                    y2 = y1 + cell_height - 20 * scale

                    draw.rounded_rectangle([x1, y1, x2, y2], radius=25*scale, fill=card_color)

                    if day_cell == 0:
                        continue

                    day_x = x1 + 35 * scale
                    day_y = y1 + 35 * scale

                    if day_cell == today.day and month == today.month and year == today.year:
                        r = 22*scale
                        draw.ellipse((day_x - r, day_y - r, day_x + r, day_y + r), fill=ios_red)
                        draw.text((day_x, day_y), str(day_cell), fill="white", font=font_day, anchor="mm")
                    else:
                        color = ios_red if col_idx >= 5 else text_color
                        draw.text((day_x, day_y), str(day_cell), fill=color, font=font_day, anchor="mm")

                    if day_cell in tasks_by_day:
                        events = tasks_by_day[day_cell]
                        max_show = 1
                        for i, (title, _, remindme) in enumerate(events[:max_show]):
                            pill_color = ios_red if remindme else ios_blue
                            pill_y = y1 + 70*scale + i*35*scale
                            draw.rounded_rectangle(
                                (x1 + 25*scale, pill_y, x2 - 25*scale, pill_y + 28*scale),
                                radius=14*scale,
                                fill=pill_color
                            )
                            draw.text((x1 + 40*scale, pill_y + 14*scale), title[:18], fill="white", font=font_event, anchor="lm")
                        if len(events) > max_show:
                            more_text = f"+{len(events)-max_show} more"
                            draw.text(
                                (x1 + 35*scale, y1 + 75*scale + max_show*35*scale),
                                more_text, fill=subtext_color, font=font_event, anchor="lm"
                            )

            draw.text(
                (width // 2, height - 35 * scale),
                f"{interaction.guild.name if scope.lower() == 'guild' else interaction.user.name}`s Tasks",
                fill=subtext_color,
                font=font_task_title,
                anchor="mm"
            )

        final_img = img.resize((1600, 1100), Image.LANCZOS)
        with io.BytesIO() as image_binary:
            final_img.save(image_binary, "PNG", optimize=True)
            image_binary.seek(0)
            return discord.File(fp=image_binary, filename="calendar.png")


async def setup(bot):
    await bot.add_cog(TaskCalendar(bot))
