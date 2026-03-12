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

        self.message: discord.Message | None = None

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

        channel_options = [
            discord.SelectOption(label=ch.name, value=str(ch.id))
            for ch in guild.text_channels
        ]

        select_channel = discord.ui.Select(
            placeholder="Select a channel",
            options=channel_options,
            required=True
        )
        select_channel.callback = self.channel_selected

        container.add_item(discord.ui.ActionRow(select_channel))

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

        save_button = discord.ui.Button(label="Save", style=discord.ButtonStyle.green)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)

        save_button.callback = self.save_clicked
        cancel_button.callback = self.cancel_clicked

        container.add_item(discord.ui.ActionRow(save_button, cancel_button))

        self.add_item(container)

    async def channel_selected(self, interaction: discord.Interaction):
        self.selected_channel = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def mode_selected(self, interaction: discord.Interaction):
        self.selected_mode = interaction.data["values"][0]
        await interaction.response.defer()

    async def save_clicked(self, interaction: discord.Interaction):

        await self.update_db()

        self._build()

        await interaction.response.edit_message(view=self)

    async def cancel_clicked(self, interaction: discord.Interaction):

        cancel_view = discord.ui.LayoutView()

        container = discord.ui.Container(accent_color=discord.Color.red().value)

        container.add_item(discord.ui.TextDisplay("# ❌ Setup canceled"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("The configuration process was aborted."))

        cancel_view.add_item(container)

        await interaction.response.edit_message(view=cancel_view)

        self.stop()

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

        channel_options = [
            discord.SelectOption(label=ch.name, value=str(ch.id))
            for ch in guild.text_channels
        ]

        select_channel = discord.ui.Select(
            placeholder="Select a channel",
            options=channel_options,
            required=True
        )

        select_channel.callback = self.channel_selected

        container.add_item(discord.ui.ActionRow(select_channel))

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

        save_button = discord.ui.Button(label="Save", style=discord.ButtonStyle.green)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)

        save_button.callback = self.save_clicked
        cancel_button.callback = self.cancel_clicked

        container.add_item(discord.ui.ActionRow(save_button, cancel_button))

        self.add_item(container)

    async def channel_selected(self, interaction: discord.Interaction):

        self.selected_channel = int(interaction.data["values"][0])
        await interaction.response.defer()

    async def mode_selected(self, interaction: discord.Interaction):

        self.selected_mode = interaction.data["values"][0]
        await interaction.response.defer()

    async def save_clicked(self, interaction: discord.Interaction):

        await interaction.response.defer()
        await self.insert_db()

        success_view = discord.ui.LayoutView()

        container = discord.ui.Container(accent_color=discord.Color.green().value)

        container.add_item(discord.ui.TextDisplay("# ✅ Configuration created"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"Reminder Channel: <#{self.selected_channel}>"))
        container.add_item(discord.ui.TextDisplay(f"Mode: {self.selected_mode.title()}"))

        success_view.add_item(container)

        await interaction.response.edit_message(view=success_view)

        self.stop()

    async def cancel_clicked(self, interaction: discord.Interaction):

        cancel_view = discord.ui.LayoutView()

        container = discord.ui.Container(accent_color=discord.Color.red().value)

        container.add_item(discord.ui.TextDisplay("# ❌ Setup canceled"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("The configuration process was aborted."))

        cancel_view.add_item(container)

        await interaction.response.edit_message(view=cancel_view)

        self.stop()

    async def insert_db(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "INSERT INTO nexory_user_config (userID, mode) VALUES (%s, %s) "
                    "ON DUPLICATE KEY UPDATE mode=%s",
                    (self.user_id, self.selected_mode, self.selected_mode)
                )
            await conn.commit()


class SetupUser(discord.ui.LayoutView):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)

        self.bot = bot
        self.user_id = user_id

        self.selected_mode = None

        self._build()

    def _build(self):

        self.clear_items()

        container = discord.ui.Container(accent_color=discord.Color.dark_blue().value)

        container.add_item(discord.ui.TextDisplay("# <:settings:1034191404487954442> - User Configuration"))
        container.add_item(discord.ui.Separator())

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

        save_button = discord.ui.Button(label="Save", style=discord.ButtonStyle.green)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)

        save_button.callback = self.save_clicked
        cancel_button.callback = self.cancel_clicked

        container.add_item(discord.ui.ActionRow(save_button, cancel_button))

        self.add_item(container)

    async def mode_selected(self, interaction: discord.Interaction):

        self.selected_mode = interaction.data["values"][0]
        await interaction.response.defer()

    async def save_clicked(self, interaction: discord.Interaction):

        await self.insert_db()

        success_view = discord.ui.LayoutView()

        container = discord.ui.Container(accent_color=discord.Color.green().value)

        container.add_item(discord.ui.TextDisplay("# ✅ User configuration saved"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"Mode: {self.selected_mode.title()}"))

        success_view.add_item(container)

        await interaction.response.edit_message(view=success_view)

        self.stop()

    async def cancel_clicked(self, interaction: discord.Interaction):

        cancel_view = discord.ui.LayoutView()

        container = discord.ui.Container(accent_color=discord.Color.red().value)

        container.add_item(discord.ui.TextDisplay("# ❌ Setup canceled"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("The configuration process was aborted."))

        cancel_view.add_item(container)

        await interaction.response.edit_message(view=cancel_view)

        self.stop()

    async def insert_db(self):

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT userID FROM nexory_user_config WHERE userID=%s", (self.user_id,))
                existing_user = await cur.fetchone()
                if existing_user:
                    await cur.execute(
                        "UPDATE nexory_user_config SET mode=%s WHERE userID=%s",
                        (self.selected_mode, self.user_id)

                    )
                else:
                    await cur.execute(
                        "INSERT INTO nexory_user_config (userID, mode) VALUES (%s, %s) ON DUPLICATE KEY UPDATE mode=%s",
                        (self.user_id, self.selected_mode, self.selected_mode)
                    )
                    
                await conn.commit()


class Setup(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @app_commands.command(name="setup", description="Start the setup process for server configuration.")
    async def setup(self, interaction: discord.Interaction):

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:

                if isinstance(interaction.channel, discord.DMChannel):

                    view = SetupUser(
                            self.bot,
                            interaction.user.id
                        )

                    await interaction.response.send_message(view=view)

                    view.message = await interaction.original_response()

                    await view.wait()
                    return

                else:

                    await cur.execute(
                        "SELECT * FROM nexory_guild_config WHERE guildID=%s",
                        (interaction.guild.id,)
                    )

                    existing_config = await cur.fetchone()

                    if existing_config:

                        view = SetupOverwrite(
                            self.bot,
                            interaction.guild.id,
                            existing_config[1],
                            existing_config[2]
                        )

                    else:

                        view = SetupCreate(
                            self.bot,
                            interaction.guild.id
                        )

                    await interaction.response.send_message(view=view)

                    view.message = await interaction.original_response()

                    await view.wait()
                


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Setup(bot))
