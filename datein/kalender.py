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
        from datetime import date
        import calendar
        import io
        from PIL import Image, ImageDraw, ImageFont
        import discord

        today = date.today()
        month = month or today.month
        year = year or today.year

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

        tasks_by_day = {}
        for title, task_date, remindme in rows:
            tasks_by_day.setdefault(task_date.day, []).append((title, remindme))

        # --- iOS Style Layout ---
        width, height = 1400, 1000
        bg_color = (245, 245, 247)  # iOS light gray
        grid_color = (220, 220, 220)
        text_color = (30, 30, 30)
        accent_color = (255, 59, 48)  # iOS red

        img = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        font_title = ImageFont.truetype("arial.ttf", 60)
        font_weekday = ImageFont.truetype("arial.ttf", 28)
        font_day = ImageFont.truetype("arial.ttf", 32)

        # Titel (zentriert, minimalistisch)
        draw.text(
            (width // 2, 60),
            f"{calendar.month_name[month]} {year}",
            fill=text_color,
            font=font_title,
            anchor="mm"
        )

        # Kalender vorbereiten
        cal = calendar.Calendar(firstweekday=0)
        month_days = cal.monthdayscalendar(year, month)

        cell_width = width // 7
        cell_height = (height - 200) // len(month_days)
        start_y = 160

        # Wochentage Header
        weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        for i, day_name in enumerate(weekdays):
            x = i * cell_width + cell_width // 2
            draw.text((x, start_y - 40), day_name, fill=(120, 120, 120), font=font_weekday, anchor="mm")

        # Grid + Inhalt
        for row_idx, week in enumerate(month_days):
            for col_idx, day in enumerate(week):
                x1 = col_idx * cell_width
                y1 = start_y + row_idx * cell_height
                x2 = x1 + cell_width
                y2 = y1 + cell_height

                # dünne iOS Linien
                draw.line((x1, y1, x2, y1), fill=grid_color)
                draw.line((x1, y1, x1, y2), fill=grid_color)

                if day != 0:
                    center_x = x1 + 40
                    center_y = y1 + 35

                    # Heutiger Tag → gefüllter Kreis
                    if day == today.day and month == today.month and year == today.year:
                        r = 22
                        draw.ellipse(
                            (center_x - r, center_y - r, center_x + r, center_y + r),
                            fill=accent_color
                        )
                        draw.text(
                            (center_x, center_y),
                            str(day),
                            fill="white",
                            font=font_day,
                            anchor="mm"
                        )
                    else:
                        draw.text(
                            (center_x, center_y),
                            str(day),
                            fill=text_color,
                            font=font_day,
                            anchor="mm"
                        )

                    # Termine als Punkte (wie iPhone)
                    if day in tasks_by_day:
                        for i, (task, remindme) in enumerate(tasks_by_day[day][:3]):
                            dot_color = accent_color if remindme else (0, 122, 255)
                            dot_y = y1 + 75 + i * 15
                            draw.ellipse(
                                (center_x - 6, dot_y - 6, center_x + 6, dot_y + 6),
                                fill=dot_color
                            )

        with io.BytesIO() as image_binary:
            img.save(image_binary, "PNG")
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="calendar.png")
            await ctx.send(
                file=file,
                content=f"**{scope.title()} Tasks Kalender** für {calendar.month_name[month]} {year}"
            )

async def setup(bot):
    await bot.add_cog(TaskCalendar(bot))