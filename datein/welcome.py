import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import aiohttp
import io
import os
import random

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="welcome_banner")
    async def welcome_banner(self, ctx, member: discord.Member):
        import os, io, aiohttp
        from PIL import Image, ImageDraw, ImageFont

        banner_path = "database/images/welcome_banner.png"
        if not os.path.exists(banner_path):
            await ctx.send("Banner-Bild nicht gefunden!")
            return

        banner = Image.open(banner_path).convert("RGBA")
        draw = ImageDraw.Draw(banner)

        avatar_url = member.display_avatar.url
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                if resp.status != 200:
                    await ctx.send("Avatar konnte nicht geladen werden.")
                    return
                avatar_bytes = await resp.read()

        avatar_size = 305
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((avatar_size, avatar_size))

        mask = Image.new("L", (avatar_size, avatar_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

        circle_center_x = 295
        circle_center_y = banner.height // 2
        avatar_x = int(circle_center_x - avatar_size / 2)
        avatar_y = int(circle_center_y - avatar_size / 2)
        banner.paste(avatar, (avatar_x, avatar_y), mask=mask)

        username = member.name
        human_members = len([m for m in member.guild.members if not m.bot])
        member_count_text = f"#{human_members}"

        fonts_dir = os.path.join(os.path.dirname(__file__), "..", "fonts")
        font_path = os.path.join(fonts_dir, "text.ttf")
        if not os.path.exists(font_path):
            await ctx.send("Font-Datei nicht gefunden!")
            return

        username_font = ImageFont.truetype(font_path, 70)
        count_font = ImageFont.truetype(font_path, 35)

        line_y = banner.height // 2

        def truncate_text(text, font, max_width):
            if font.getlength(text) <= max_width:
                return text
            while font.getlength(text + "...") > max_width and len(text) > 0:
                text = text[:-1]
            return text + "..." if text else ""

        username_length = username_font.getlength(username)

        char = "#"
        char_width = count_font.getlength(char)

        username_start_x = circle_center_x + avatar_size // 2 + 240
        count_start_x = username_start_x + username_length // 2 - char_width // 2
        max_width = 400

        username = truncate_text(username, username_font, max_width)
        member_count_text = truncate_text(member_count_text, count_font, max_width)

        username_x = username_start_x
        count_x = count_start_x

        username_y = line_y - 90
        count_y = line_y + 25

        draw.text((username_x, username_y), username, font=username_font, fill="white")
        draw.text((count_x, count_y), member_count_text, font=count_font, fill="white")

        with io.BytesIO() as image_binary:
            banner.save(image_binary, "PNG")
            image_binary.seek(0)
            file = discord.File(fp=image_binary, filename="welcome_banner.png")
            await ctx.send(file=file)

async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))