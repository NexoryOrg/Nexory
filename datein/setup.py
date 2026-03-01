import discord
from discord.ext import commands
from discord import app_commands

class SetupOverwrite(discord.ui.LayoutView):
    def __init__(self, bot, guild_id: int, reminde_channel_id: int, mode: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.selected_channel = reminde_channel_id
        self.selected_mode = mode

        self._build()

    def _build(self):
        self.clear_items()
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return

        container = discord.ui.Container(accent_color=discord.Color.dark_blue().value)
        container.add_item(discord.ui.TextDisplay("# <:settings:1034191404487954442> - Overwrite Configuration"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"### Existing reminder channel: <#{self.selected_channel}>"))

        # Channel Select
        channel_options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in guild.text_channels]
        select_channel = discord.ui.Select(
            placeholder="Select a channel",
            options=channel_options,
            required=True
        )
        select_channel.callback = self.channel_selected
        container.add_item(discord.ui.ActionRow(select_channel))

        # Mode Select
        container.add_item(discord.ui.TextDisplay(f"### Existing mode: {self.selected_mode.title()}"))
        mode_options = [
            discord.SelectOption(label="Light", value="light"),
            discord.SelectOption(label="Dark", value="dark")
        ]
        select_mode = discord.ui.Select(
            placeholder="Select mode",
            options=mode_options,
            required=True
        )
        select_mode.callback = self.mode_selected
        container.add_item(discord.ui.ActionRow(select_mode))

        # Save + Cancel Buttons in ActionRow
        save_button = discord.ui.Button(label="Save", style=discord.ButtonStyle.green, custom_id="save")
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel")
        buttons_row = discord.ui.ActionRow(save_button, cancel_button)
        container.add_item(buttons_row)

        self.add_item(container)

    async def channel_selected(self, interaction: discord.Interaction):
        self.selected_channel = int(interaction.data['values'][0])
        await interaction.response.defer()

    async def mode_selected(self, interaction: discord.Interaction):
        self.selected_mode = interaction.data['values'][0]
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id")
        if cid == "save":
            await self.update_db()
            await interaction.response.send_message("Configuration saved!", ephemeral=True)
            self.stop()
            return False
        elif cid == "cancel":
            await interaction.response.send_message("Setup canceled.", ephemeral=True)
            self.stop()
            return False
        return True

    async def update_db(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "UPDATE nexory_guild_config SET reminde_channel=%s, mode=%s WHERE guildID=%s",
                    (self.selected_channel, self.selected_mode, self.guild_id)
                )
                await conn.commit()


class SetupCreate(discord.ui.LayoutView):
    def __init__(self, bot, guild_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.selected_channel = None
        self.selected_mode = None

        self._build()

    def _build(self):
        self.clear_items()
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return

        container = discord.ui.Container(accent_color=discord.Color.dark_blue().value)
        container.add_item(discord.ui.TextDisplay("# <:settings:1034191404487954442> - Create Configuration"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("### Select reminder channel"))

        # Channel Select
        channel_options = [discord.SelectOption(label=ch.name, value=str(ch.id)) for ch in guild.text_channels]
        select_channel = discord.ui.Select(
            placeholder="Select a channel",
            options=channel_options,
            required=True
        )
        select_channel.callback = self.channel_selected
        container.add_item(discord.ui.ActionRow(select_channel))

        # Mode Select
        container.add_item(discord.ui.TextDisplay("### Select mode"))
        mode_options = [
            discord.SelectOption(label="Light", value="light"),
            discord.SelectOption(label="Dark", value="dark")
        ]
        select_mode = discord.ui.Select(
            placeholder="Select mode",
            options=mode_options,
            required=True
        )
        select_mode.callback = self.mode_selected
        container.add_item(discord.ui.ActionRow(select_mode))

        # Save + Cancel Buttons
        save_button = discord.ui.Button(label="Save", style=discord.ButtonStyle.green, custom_id="save")
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel")
        buttons_row = discord.ui.ActionRow(save_button, cancel_button)
        container.add_item(buttons_row)

        self.add_item(container)

    async def channel_selected(self, interaction: discord.Interaction):
        self.selected_channel = int(interaction.data['values'][0])
        await interaction.response.defer()

    async def mode_selected(self, interaction: discord.Interaction):
        self.selected_mode = interaction.data['values'][0]
        await interaction.response.defer()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cid = interaction.data.get("custom_id")
        if cid == "save":
            await self.insert_db()
            await interaction.response.send_message("Configuration created!", ephemeral=True)
            self.stop()
            return False
        elif cid == "cancel":
            await interaction.response.send_message("Setup canceled.", ephemeral=True)
            self.stop()
            return False
        return True

    async def insert_db(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO nexory_guild_config (guildID, reminde_channel, mode) VALUES (%s, %s, %s)",
                    (self.guild_id, self.selected_channel, self.selected_mode)
                )
                await conn.commit()


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    @app_commands.command(name="setup", description="Start the setup process for server configuration.")
    async def setup(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM nexory_guild_config WHERE guildID=%s",
                    (interaction.guild.id,)
                )
                existing_config = await cur.fetchone()
                if existing_config:
                    view = SetupOverwrite(self.bot, interaction.guild.id, existing_config[1], existing_config[2])
                else:
                    view = SetupCreate(self.bot, interaction.guild.id)

                await interaction.response.send_message(view=view)
                await view.wait()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))