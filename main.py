import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
import aiomysql

load_dotenv()
token = os.getenv("TOKEN")
db_host = os.getenv("DB_HOST")
db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_name = os.getenv("DB_NAME")


class MainDatei(commands.Bot):

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.presences = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        geladene_cogs = 0
        cog_files = [f for f in os.listdir("datein") if f.endswith(".py")]
        print(f"Gefundene Cogs: {len(cog_files)}")
        for filename in cog_files:
            await self.load_extension(f"datein.{filename[:-3]}")
            geladene_cogs += 1
            print(f"Cog geladen: {filename} ({geladene_cogs}/{len(cog_files)})")

        print("Verbindung zur Datenbank wird aufgebaut...")
        try:
            print(db_host, db_user, db_name)
            self.pool = await aiomysql.create_pool(
                host=db_host,
                port=3306,
                user=db_user,
                password=db_password,
                db=db_name,
                minsize=1,
                maxsize=10,
                autocommit=True, 
                connect_timeout=10, 
                pool_recycle=300
            )
            print("✅ Datenbank verbunden!")
        except Exception as e:
            print(f"❌ Fehler bei der Datenbankverbindung: {e}")
            return
        
    
        async with self.pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS nexory_user_tasks("
                    "userID BIGINT, title VARCHAR(50), des LONGTEXT, date DATE, remindme BOOLEAN DEFAULT FALSE)"
                )
                print("Tabelle nexory_user_tasks überprüft/erstellt")

                await cur.execute(
                    "CREATE TABLE IF NOT EXISTS nexory_guild_tasks("
                    "guildID BIGINT, title VARCHAR(50), des LONGTEXT, date DATE, remindme BOOLEAN DEFAULT FALSE)"
                )
                print("Tabelle nexory_guild_tasks überprüft/erstellt")


    async def on_ready(self):
        print(f"✅ Eingeloggt als {self.user}")


bot = MainDatei()


async def main():
    async with bot:
        await bot.start(token)

@bot.command()
@commands.is_owner()
async def dbtest(ctx: commands.Context):
    try:
        async with bot.pool.acquire() as conn:
            await conn.ping(reconnect=True)
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                if result:
                    await ctx.send("✅ Datenbankverbindung ist aktiv!")
                else:
                    await ctx.send("❌ Datenbankverbindung ist nicht aktiv!")
    except Exception as e:
        await ctx.send(f"❌ Fehler bei der Datenbankverbindung: {e}")

if __name__ == "__main__":
    asyncio.run(main())
