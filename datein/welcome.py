import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import aiohttp
import io
import os
import random

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def welcome_test(self, ctx, member: discord.Member):
        channel = self.bot.get_channel(1474787091769458893)
        if not channel:
            await ctx.send("Kanal nicht gefunden!")
            return

        # Banner-Größe
        width, height = 900, 250
        image = Image.new("RGB", (width, height), (54, 57, 82))

        # Hintergrundverlauf (Dunkelblau → Lila)
        for y in range(height):
            r = int(54 + (87-54) * y/height)
            g = int(57 + (70-57) * y/height)
            b = int(82 + (238-82) * y/height)
            ImageDraw.Draw(image).line([(0, y), (width, y)], fill=(r, g, b))

        draw = ImageDraw.Draw(image)

        # Schriftarten
        font_path = os.path.join(os.path.dirname(__file__), "..", "fonts", "text.ttf")
        font_path = os.path.abspath(font_path)
        if not os.path.exists(font_path):
            await ctx.send("Font-Datei nicht gefunden!")
            return
        font_title = ImageFont.truetype(font_path, 60)
        font_subtitle = ImageFont.truetype(font_path, 30)
        font_number = ImageFont.truetype(font_path, 25)

        # Avatar abrufen
        async with aiohttp.ClientSession() as session:
            async with session.get(str(member.avatar.url)) as resp:
                avatar_bytes = await resp.read()
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        avatar = avatar.resize((180, 180))

        # Rund + Schatten
        mask = Image.new("L", avatar.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0) + avatar.size, fill=255)
        avatar.putalpha(mask)

        # Glow hinter Avatar
        glow = Image.new("RGBA", (200, 200), (100, 100, 255, 60))
        glow_mask = Image.new("L", glow.size, 0)
        draw_glow = ImageDraw.Draw(glow_mask)
        draw_glow.ellipse((0, 0, 200, 200), fill=255)
        glow.putalpha(glow_mask)
        glow = glow.filter(ImageFilter.GaussianBlur(15))
        image.paste(glow, (20, 35), glow)

        # Avatar einfügen
        image.paste(avatar, (30, 35), avatar)

        # Texte einfügen
        # Nummer oben rechts
        users = [user for user in channel.guild.members if not user.bot]
        draw.text((width-80, 20), f"#{len(users)}", font=font_number, fill=(50,50,50))

        # Willkommen
        draw.text((250, 30), "WILLKOMMEN", font=font_title, fill=(255, 255, 255))

        # Untertitel
        subtitle_text = f"Schön, dass du da bist {member.name}!"
        draw.text((250, 100), subtitle_text, font=font_subtitle, fill=(200,200,200))

        # Dekorative Sterne
        for _ in range(25):
            x = random.randint(400, width-50)
            y = random.randint(10, height-30)
            r = random.randint(2,4)
            draw.ellipse((x-r, y-r, x+r, y+r), fill=(255,255,255,150))

        # Senden
        with io.BytesIO() as image_binary:
            image.save(image_binary, "PNG")
            image_binary.seek(0)
            await channel.send(file=discord.File(fp=image_binary, filename="welcome.png"))

async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))