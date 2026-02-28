import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import calendar
from datetime import date
import io

class TaskCalendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def kalender(self, ctx, scope: str = "user", month: int = None, year: int = None):
        """
        Zeigt einen Kalender mit Tasks.
        scope: 'user' oder 'guild'
        month, year optional, Standard = aktueller Monat/Jahr
        """
        today = date.today()
        month = month or today.month
        year = year or today.year

        # Daten aus DB holen
        if scope.lower() == "guild":
            query = "SELECT title, date, remindme FROM nexory_guild_tasks WHERE date BETWEEN %s AND %s AND guildID=%s"
            params = (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]), ctx.guild.id)
        else:
            query = "SELECT title, date, remindme FROM nexory_user_tasks WHERE date BETWEEN %s AND %s AND userID=%s"
            params = (date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]), ctx.author.id)

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()

        # Termine nach Tag sortieren
        tasks_by_day = {}
        for title, task_date, remindme in rows:
            day = task_date.day
            tasks_by_day.setdefault(day, []).append((title, remindme))

        # --- PIL Kalender erstellen ---
        width, height = 1400, 1000
        img = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(img)

        font_title = ImageFont.truetype("arial.ttf", 60)
        font_day = ImageFont.truetype("arial.ttf", 30)
        font_task = ImageFont.truetype("arial.ttf", 20)

        draw.text((width // 2, 50), f"{calendar.month_name[month]} {year}", fill="black", font=font_title, anchor="mm")

        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(year, month)

        cell_width = width // 7
        cell_height = (height - 150) // len(month_days)
        start_y = 150

        for row_idx, week in enumerate(month_days):
            for col_idx, day in enumerate(week):
                x1 = col_idx * cell_width
                y1 = start_y + row_idx * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height

                draw.rectangle([x1, y1, x2, y2], outline="black")

                if day != 0:
                    # Tag anzeigen
                    draw.text((x1 + 10, y1 + 5), str(day), fill="black", font=font_day)

                    # Heutigen Tag hervorheben
                    if day == today.day and month == today.month and year == today.year:
                        draw.rectangle([x1, y1, x2, y2], outline="red", width=4)

                    # Termine eintragen
                    if day in tasks_by_day:
                        for i, (task, remindme) in enumerate(tasks_by_day[day]):
                            color = "blue" if not remindme else "red"
                            draw.text((x1 + 10, y1 + 40 + i * 22), task[:20], fill=color, font=font_task)

        # In BytesIO speichern, um Discord Attachment zu senden
        with io.BytesIO() as image_binary:
            img.save(image_binary, "PNG")
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="calendar.png")
            await ctx.send(file=file, content=f"**{scope.title()} Tasks Kalender** für {calendar.month_name[month]} {year}")

# Cog hinzufügen
async def setup(bot):
    await bot.add_cog(TaskCalendar(bot))