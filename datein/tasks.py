import discord
import logging
from discord.ext import commands, tasks
from discord import app_commands, ui, Interaction, Embed, ButtonStyle
from datetime import datetime
import pytz
import math
from typing import Literal
import aiomysql


# Logger setup
logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename="logs/discord.log", encoding="utf-8")
datum_format = "%Y-%m-%d %H-%M-%S"
formatieren = logging.Formatter(
    "[{asctime}] [{levelname:<8}] {name}: {message}",
    datum_format,
    style="{"
)
handler.setFormatter(formatieren)
logger.addHandler(handler)
                

# Helper function to send error messages
async def send_error(interaction, error, embed_description: str,
                     embed_color: discord.Color,
                     embed_icon_url: str,
                     embed_author: str,
                     embed_footer: str):

    embed = discord.Embed(
        description=embed_description,
        color=embed_color,
        timestamp=datetime.now()
    )

    embed.set_author(name=embed_author, icon_url=embed_icon_url)
    embed.set_footer(text=embed_footer)

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

    logger.error(f"Unbekannter Fehler aufgetreten! {error}")


#Create Task Modal & View
class CreateModal(discord.ui.Modal, title="📩 - Create Task"):
    def __init__(self, table_type: str):
        super().__init__()
        self.table_type = table_type
        self.title_modal = discord.ui.TextInput(label="Task Title", placeholder="e.g. program a Discord bot", max_length=50, required=True)
        self.des = discord.ui.TextInput(label="Task Description", placeholder="e.g. programm a Discord bot für NexoryOrg (moderation and logging)", max_length=500, required=True)
        self.time = discord.ui.TextInput(label="Finish date", placeholder="YYYY-MM-DD", max_length=10, required=True)
        self.remindme = discord.ui.TextInput(label="Remind me", placeholder="Type 'yes' if you want to be reminded", max_length=3, required=False)
        self.add_item(self.title_modal)
        self.add_item(self.des)
        self.add_item(self.time)
        self.add_item(self.remindme)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            date = datetime.strptime(self.time.value, "%Y-%m-%d").date()
            today = datetime.now().date()
            if date <= today:
                return await interaction.response.send_message("⛔ - The date must be in the future! Please enter a future date.", ephemeral=True)
            remindme_bool = self.remindme.value.lower() == "yes"
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if self.table_type == "user":
                        table_name = "nexory_user_tasks"
                        table_term = "userID"
                        id_value = interaction.user.id
                    else:
                        table_name = "nexory_guild_tasks"
                        table_term = "guildID"
                        id_value = interaction.guild.id
                    await cur.execute(f"SELECT 1 FROM {table_name} WHERE {table_term}=%s AND title=%s", (id_value, self.title_modal.value))
                    if await cur.fetchone():
                        return await interaction.response.send_message("⛔ - Please don't create the same task twice.", ephemeral=True)
            if self.table_type == "guild":
                async with interaction.client.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT tag FROM nexory_guild_custom_tags WHERE guildID=%s", (interaction.guild.id,))
                        rows = await cur.fetchall()
                db_tags = [r[0] for r in rows] if rows else []
                fixed_tags = ["#termin", "#task", "#work"]
                all_tags = db_tags + fixed_tags
            else:
                all_tags = ["#termin", "#task", "#work"]
            await interaction.response.send_message(
                view=CreateView(
                    client=interaction.client,
                    table_type=self.table_type,
                    title=self.title_modal.value,
                    des=self.des.value,
                    date=date,
                    remindme=remindme_bool,
                    guild=interaction.guild if self.table_type=="guild" else None,
                    tag_options=all_tags
                ),
                ephemeral=True
            )
        except Exception as e:
            await send_error(interaction, e, "Es ist ein unbekannter Fehler aufgetreten.", discord.Color.red(), interaction.user.display_avatar.url, "Fehlermeldung", "https://github.com/NexoryOrg")

class CreateView(discord.ui.LayoutView):
    def __init__(self, client, table_type: str, title: str, des: str, date: datetime, remindme: bool, guild, tag_options):
        super().__init__(timeout=300)
        self.client = client
        self.table_type = table_type
        self.title = title
        self.des = des
        self.date = date
        self.remindme = remindme
        self.guild = guild
        self.selected_tag = None
        self.selected_priority = None
        self.tag_options = tag_options
        self._build()

    def _build(self):
        self.clear_items()
        container = discord.ui.Container(accent_color=discord.Color.green().value)
        container.add_item(discord.ui.TextDisplay("# 📩 - Create Task"))
        container.add_item(discord.ui.Separator())
        self.tag_select = discord.ui.Select(
            placeholder="Select a tag for the task",
            options=[discord.SelectOption(label=tag, value=tag) for tag in self.tag_options]
        )
        async def tag_callback(interaction: discord.Interaction):
            self.selected_tag = self.tag_select.values[0]
            await interaction.response.defer()
        self.tag_select.callback = tag_callback
        container.add_item(discord.ui.ActionRow(self.tag_select))
        self.priority_select = discord.ui.Select(
            placeholder="Select a priority for the task",
            options=[
                discord.SelectOption(label="Not important", value="not important"),
                discord.SelectOption(label="Normal", value="normal"),
                discord.SelectOption(label="Important", value="important")
            ]
        )
        async def priority_callback(interaction: discord.Interaction):
            self.selected_priority = self.priority_select.values[0]
            await interaction.response.defer()
        self.priority_select.callback = priority_callback
        container.add_item(discord.ui.ActionRow(self.priority_select))
        save_btn = discord.ui.Button(label="Save", style=discord.ButtonStyle.green)
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
        save_btn.callback = self.save_clicked
        cancel_btn.callback = self.cancel_clicked
        container.add_item(discord.ui.ActionRow(save_btn, cancel_btn))
        self.add_item(container)

    async def save_clicked(self, interaction: discord.Interaction):
        if not self.selected_tag or not self.selected_priority:
            self.selected_priority = "normal"

        async with self.client.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if self.table_type == "user":
                    table_name = "nexory_user_tasks"
                    table_term = "userID"
                    id_value = interaction.user.id
                else:
                    table_name = "nexory_guild_tasks"
                    table_term = "guildID"
                    id_value = interaction.guild.id
                await cur.execute(
                    f"INSERT INTO {table_name} ({table_term}, title, des, date, remindme, tag, priority) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (id_value, self.title, self.des, self.date, self.remindme, self.selected_tag, self.selected_priority)
                )
                await conn.commit()
        success_view = discord.ui.LayoutView()
        container = discord.ui.Container(accent_color=discord.Color.green().value)
        container.add_item(discord.ui.TextDisplay(f"# ✅ Task '{self.title}' created!"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"**Tag**: {self.selected_tag}"))
        container.add_item(discord.ui.TextDisplay(f"**Priority**: {self.selected_priority}"))
        success_view.add_item(container)
        await interaction.response.edit_message(view=success_view)
        self.stop()

    async def cancel_clicked(self, interaction: discord.Interaction):
        cancel_view = discord.ui.LayoutView()
        container = discord.ui.Container(accent_color=discord.Color.red().value)
        container.add_item(discord.ui.TextDisplay("# ❌ Task creation canceled"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("The configuration process was aborted."))
        cancel_view.add_item(container)
        await interaction.response.edit_message(view=cancel_view)
        self.stop()


#Edit Task Modal & View
class EditModal(discord.ui.Modal, title="📝 - Edit Task"):

    def __init__(self, table_type: str, title: str, view: "TaskView", guild=None):
        super().__init__()
        self.table_type = table_type
        self.original_title = title
        self.view = view
        self.guild = guild
        self.title_value = None
        self.selected_tag = None
        self.selected_priority = None

        self.edit_title_modal = discord.ui.TextInput(
            label=f"Task Title (old: {title})",
            max_length=50,
            placeholder="Leave empty to keep the same title",
            required=False
        )

        self.edit_des = discord.ui.TextInput(
            label="Task Description",
            max_length=500,
            placeholder="Leave empty to keep the same description",
            required=False
        )

        self.edit_time = discord.ui.TextInput(
            label="Finish date",
            placeholder="YYYY-MM-DD, leave empty to keep the same date",
            max_length=10,
            required=False
        )

        self.remindme = discord.ui.TextInput(
            label="Remind me",
            placeholder="Type 'no' if you don't want to be reminded",
            max_length=3,
            required=False
        )

        self.add_item(self.edit_title_modal)
        self.add_item(self.edit_des)
        self.add_item(self.edit_time)
        self.add_item(self.remindme)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            async with interaction.client.pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if self.table_type == "user":
                        table_name = "nexory_user_tasks"
                        table_term = "userID"
                        id_value = interaction.user.id
                    else:
                        table_name = "nexory_guild_tasks"
                        table_term = "guildID"
                        id_value = interaction.guild.id

                    await cur.execute(
                        f"SELECT title, des, date, remindme, tag, priority FROM {table_name} WHERE {table_term}=%s AND title=%s",
                        (id_value, self.original_title)
                    )
                    row = await cur.fetchone()
                    if not row:
                        return await interaction.response.send_message("⛔ - Task not found.", ephemeral=True)

                    old_title, old_des, old_date, old_remind, old_tag, old_priority = row

                    new_title = self.edit_title_modal.value.strip() or old_title
                    new_des = self.edit_des.value.strip() or old_des
                    if self.edit_time.value.strip():
                        try:
                            edit_date = datetime.strptime(self.edit_time.value.strip(), "%Y-%m-%d").date()
                            if edit_date <= datetime.now().date():
                                return await interaction.response.send_message("⛔ - The date must be in the future!", ephemeral=True)
                        except ValueError:
                            return await interaction.response.send_message("⛔ - Invalid date format! Use YYYY-MM-DD.", ephemeral=True)
                    else:
                        edit_date = old_date

                    if self.remindme.value.strip():
                        new_remind = True if self.remindme.value.strip().lower() == "yes" else False
                    else:
                        new_remind = old_remind

                    if new_title != old_title:
                        await cur.execute(f"SELECT 1 FROM {table_name} WHERE {table_term}=%s AND title=%s", (id_value, new_title))
                        if await cur.fetchone():
                            return await interaction.response.send_message("⛔ - A task with that title already exists.", ephemeral=True)

                    if self.table_type == "guild":
                        await cur.execute("SELECT tag FROM nexory_guild_custom_tags WHERE guildID=%s", (interaction.guild.id,))
                        rows = await cur.fetchall()
                        db_tags = [r[0] for r in rows] if rows else []
                        fixed_tags = ["#termin", "#task", "#work"]
                        all_tags = db_tags + fixed_tags
                        self.selected_tag = old_tag if old_tag in all_tags else None
                    else:
                        all_tags = ["#termin", "#task", "#work"]
                        self.selected_tag = old_tag


                    priority_options = ["not important", "normal", "important"]
                    self.selected_priority = old_priority if old_priority in priority_options else "normal"

                    await cur.execute(
                        f"UPDATE {table_name} SET title=%s, des=%s, date=%s, remindme=%s WHERE {table_term}=%s AND title=%s",
                        (new_title, new_des, edit_date, new_remind, id_value, old_title)
                    )
                    await conn.commit()

            await interaction.response.send_message(
                view=EditView(
                    bot=interaction.client,
                    table_type=self.table_type,
                    title=new_title,
                    des=new_des,
                    date=edit_date,
                    remindme=new_remind,
                    guild=interaction.guild,
                    selected_tag=self.selected_tag,
                    selected_priority=self.selected_priority,
                    tag_options=all_tags
                ),
                ephemeral=True
            )


        except Exception as e:
            await send_error(interaction, e, "Es ist ein unbekannter Fehler aufgetreten.", discord.Color.red(), interaction.user.display_avatar.url, "Fehlermeldung", "https://github.com/NexoryOrg")

class EditView(discord.ui.LayoutView):
    def __init__(self, bot, table_type, title, des, date, remindme, guild, selected_tag, selected_priority, tag_options):
        super().__init__(timeout=300)
        self.bot = bot
        self.table_type = table_type
        self.title = title
        self.des = des
        self.date = date
        self.remindme = remindme
        self.guild = guild
        self.selected_tag = selected_tag
        self.selected_priority = selected_priority
        self.tag_options = tag_options
        self._build()

    def _build(self):
        self.clear_items()
        container = discord.ui.Container(accent_color=discord.Color.green().value)
        container.add_item(discord.ui.TextDisplay(f"# `🔁` - Task **{self.title}** updated!\nDo you want to edit Tag & Priority?"))
        container.add_item(discord.ui.Separator())

        container.add_item(discord.ui.TextDisplay(f"**Edit Tag (old: {self.selected_tag})**:"))

        self.tag_select = discord.ui.Select(
            placeholder="Select a tag",
            options=[discord.SelectOption(label=tag, value=tag) for tag in self.tag_options],
        )
        async def tag_callback(interaction: discord.Interaction):
            self.selected_tag = self.tag_select.values[0]
            await interaction.response.defer()
        self.tag_select.callback = tag_callback
        container.add_item(discord.ui.ActionRow(self.tag_select))

        container.add_item(discord.ui.TextDisplay(f"**Edit priority (old: {self.selected_priority})**:"))

        self.priority_select = discord.ui.Select(
            placeholder="Select priority",
            options=[
                discord.SelectOption(label="Not important", value="not important"),
                discord.SelectOption(label="Normal", value="normal"),
                discord.SelectOption(label="Important", value="important")
            ],
        )
        async def priority_callback(interaction: discord.Interaction):
            self.selected_priority = self.priority_select.values[0]
            await interaction.response.defer()
        self.priority_select.callback = priority_callback
        container.add_item(discord.ui.ActionRow(self.priority_select))

        save_btn = discord.ui.Button(label="Save", style=discord.ButtonStyle.green)
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
        save_btn.callback = self.save_clicked
        cancel_btn.callback = self.cancel_clicked
        container.add_item(discord.ui.ActionRow(save_btn, cancel_btn))

        self.add_item(container)

    async def save_clicked(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                table_name = "nexory_guild_tasks" if self.table_type=="guild" else "nexory_user_tasks"
                table_term = "guildID" if self.table_type=="guild" else "userID"
                id_value = self.guild.id if self.table_type=="guild" else interaction.user.id
                await cur.execute(
                    f"UPDATE {table_name} SET title=%s, des=%s, date=%s, remindme=%s, tag=%s, priority=%s WHERE {table_term}=%s AND title=%s",
                    (self.title, self.des, self.date, self.remindme, self.selected_tag, self.selected_priority, id_value, self.title)
                )
                await conn.commit()
        success_view = discord.ui.LayoutView()
        container = discord.ui.Container(accent_color=discord.Color.green().value)
        container.add_item(discord.ui.TextDisplay(f"# ✅ Task '{self.title}' updated!"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"Tag: {self.selected_tag}"))
        container.add_item(discord.ui.TextDisplay(f"Priority: {self.selected_priority}"))
        success_view.add_item(container)
        await interaction.response.edit_message(view=success_view)
        self.stop()

    async def cancel_clicked(self, interaction: discord.Interaction):
        cancel_view = discord.ui.LayoutView()
        container = discord.ui.Container(accent_color=discord.Color.red().value)
        container.add_item(discord.ui.TextDisplay("# ❌ Edit canceled"))
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay("The configuration process was aborted."))
        cancel_view.add_item(container)
        await interaction.response.edit_message(view=cancel_view)
        self.stop()


#Tasklist management View
class TaskListView(ui.View):
    def __init__(self, tasks, scope, userID):
        super().__init__(timeout=300)
        self.tasks = tasks
        self.scope = scope
        self.userID = userID
        self.current_page = 0
        self.tasks_per_page = 5
        self.max_page = math.ceil(len(tasks) / self.tasks_per_page) - 1

        self.previous_button.disabled = True
        if len(tasks) <= self.tasks_per_page:
            self.next_button.disabled = True

    def get_embed(self):
        start = self.current_page * self.tasks_per_page
        end = start + self.tasks_per_page
        page_tasks = self.tasks[start:end]

        title = "Start" if self.current_page == 0 else f"Page {self.current_page + 1}/{self.max_page + 1}"

        embed = Embed(
            title=f"{self.scope.title()} Tasks - {title}",
            color=discord.Color.dark_blue(),
            timestamp=datetime.now()
        )

        for t_title, des, date in page_tasks:
            embed.add_field(
                name=f"__Title: {t_title}__",
                value=f"Description:\n*{des}*\nDue:\n*{date}*",
                inline=False
            )

        embed.set_footer(text='Use the edit option in "/task" to view details about each task.')
        embed.set_author(name="Task List")
        return embed

    @ui.button(label="⬅️", style=discord.ButtonStyle.primary, row=0)
    async def previous_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.userID:
            await interaction.response.send_message("You cannot control this pagination.", ephemeral=True)
            return

        self.current_page = max(self.current_page - 1, 0)

        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_page

        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @ui.button(label="➡️", style=discord.ButtonStyle.primary, row=0)
    async def next_button(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user.id != self.userID:
            await interaction.response.send_message("You cannot control this pagination.", ephemeral=True)
            return

        self.current_page = min(self.current_page + 1, self.max_page)
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_page

        await interaction.response.edit_message(embed=self.get_embed(), view=self)


#Task Management View
class TaskView(discord.ui.LayoutView):
    def __init__(self, bot, table_type: str, user_id=None, guild_id=None):
        super().__init__(timeout=300)
        self.bot = bot
        self.table_type = table_type
        self.user_id = user_id
        self.guild_id = guild_id
        self.tasks = []
        self.mode = None
        self.value = None
        self.message = None

    async def setup(self):
        await self.load_tasks()
        self._build()

    async def load_tasks(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if self.table_type == "user":
                    await cur.execute(
                        "SELECT title FROM nexory_user_tasks WHERE userID = %s",
                        (self.user_id,)
                    )
                elif self.table_type == "guild":
                    await cur.execute(
                        "SELECT title FROM nexory_guild_tasks WHERE guildID = %s",
                        (self.guild_id,)
                    )
                self.tasks = await cur.fetchall()

    async def delete_task(self):
        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                if self.table_type == "user":
                    await cur.execute(
                        "DELETE FROM nexory_user_tasks WHERE userID = %s AND title = %s",
                        (self.user_id, self.value)
                    )
                elif self.table_type == "guild":
                    await cur.execute(
                        "DELETE FROM nexory_guild_tasks WHERE guildID = %s AND title = %s",
                        (self.guild_id, self.value)
                    )
                await conn.commit()

    async def refresh_view(self, interaction: discord.Interaction):
        await self.load_tasks()
        self.mode = None
        self.value = None
        self._build()
        if self.message:
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message(view=self, ephemeral=True)

    def _build(self):
        self.clear_items()

        if self.mode is None:
            container = discord.ui.Container(
                accent_color=discord.Color.dark_blue().value
            )

            container.add_item(discord.ui.TextDisplay(f"# <:settings:1034191404487954442> - Manage Tasks ({self.table_type})"))
            container.add_item(discord.ui.Separator())

            create_btn = discord.ui.Button(
                label="Create",
                style=discord.ButtonStyle.secondary
            )

            async def create_cb(interaction: discord.Interaction):
                modal = CreateModal(self.table_type)
                await interaction.response.send_modal(modal)

            create_btn.callback = create_cb

            container.add_item(discord.ui.TextDisplay("### Create Task"))
            container.add_item(discord.ui.ActionRow(create_btn))

            container.add_item(discord.ui.TextDisplay("### Edit Task"))

            if self.tasks:
                options = [
                    discord.SelectOption(label=t[0], value=t[0])
                    for t in self.tasks
                ]
            else:
                options = [
                    discord.SelectOption(
                        label="No tasks available",
                        value="none"
                    )
                ]

            select_edit = discord.ui.Select(
                placeholder="Select a Task to edit",
                options=options
            )

            async def edit_sc(interaction: discord.Interaction):
                value = select_edit.values[0]

                if value == "none":
                    return await interaction.response.send_message(
                        "No tasks available.",
                        ephemeral=True
                    )

                modal = EditModal(self.table_type, value, view=self)
                await interaction.response.send_modal(modal)

            select_edit.callback = edit_sc
            container.add_item(discord.ui.ActionRow(select_edit))

            container.add_item(discord.ui.TextDisplay("### Delete Task"))

            select_delete = discord.ui.Select(
                placeholder="Select a Task to delete",
                options=options
            )

            async def delete_sc(interaction: discord.Interaction):
                value = select_delete.values[0]

                if value == "none":
                    return await interaction.response.send_message(
                        "No tasks available.",
                        ephemeral=True
                    )

                self.mode = "delete"
                self.value = value
                self._build()
                await interaction.response.edit_message(view=self)

            select_delete.callback = delete_sc
            container.add_item(discord.ui.ActionRow(select_delete))

            container.add_item(discord.ui.TextDisplay("### Show Tasks"))

            if self.tasks:
                options_list = [
                    discord.SelectOption(label=t[0], value=t[0])
                    for t in self.tasks
                ]
            else:
                options_list = [
                    discord.SelectOption(label="No tasks available", value="none")
                ]

            select_list = discord.ui.Select(
                placeholder="Select a Task to view",
                options=options_list
            )

            async def list_sc(interaction: discord.Interaction):
                value = select_list.values[0]

                if value == "none":
                    return await interaction.response.send_message(
                        "No tasks available.",
                        ephemeral=True
                    )

                async with self.bot.pool.acquire() as conn:
                    async with conn.cursor() as cur:
                        if self.table_type == "user":
                            table_name = "nexory_user_tasks"
                            table_term = "userID"
                            id_value = self.user_id
                        else:
                            table_name = "nexory_guild_tasks"
                            table_term = "guildID"
                            id_value = self.guild_id

                        await cur.execute(
                            f"SELECT title, des, date, remindme, tag, status, priority FROM {table_name} WHERE {table_term}=%s AND title=%s",
                            (id_value, value)
                        )
                        row = await cur.fetchone()

                if row:
                    title, des, date, remind, tag, status, priority = row

                    if remind == 1:
                        remind = "Yes"

                    else:
                        remind = "No"

                    embed = discord.Embed(
                        title=f"Show Task",
                        description=f"Informations about the Task **{title}**",
                        color=discord.Color.dark_blue(),
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="Description", value=des, inline=False)
                    embed.add_field(name="Finish Date", value=date, inline=False)
                    embed.add_field(name="Remind me", value=remind, inline=False)
                    embed.add_field(name="Tag", value=tag, inline=False)
                    embed.add_field(name="Status", value=status, inline=False)
                    embed.add_field(name="Priority", value=priority, inline=False)
                    embed.set_footer(text="https://github.com/NexoryOrg")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.response.send_message(
                        "Task not found.",
                        ephemeral=True
                    )

            select_list.callback = list_sc
            container.add_item(discord.ui.ActionRow(select_list))

        elif self.mode == "delete":
            container = discord.ui.Container(
                accent_color=discord.Color.red().value
            )

            container.add_item(discord.ui.TextDisplay("# Delete Task"))
            container.add_item(discord.ui.Separator())
            container.add_item(
                discord.ui.TextDisplay(
                    f"### Are you sure you want to delete the task:\n*{self.value}*"
                )
            )

            submit_btn = discord.ui.Button(
                label="Submit",
                style=discord.ButtonStyle.success
            )

            cancel_btn = discord.ui.Button(
                label="Cancel",
                style=discord.ButtonStyle.danger
            )

            async def submit_cb(interaction: discord.Interaction):
                await self.delete_task()
                await self.refresh_view(interaction)
                

            async def cancel_cb(interaction: discord.Interaction):
                await self.refresh_view(interaction)

            submit_btn.callback = submit_cb
            cancel_btn.callback = cancel_cb

            container.add_item(
                discord.ui.ActionRow(submit_btn, cancel_btn)
            )

        self.add_item(container)


class tasks(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.reminder_loop.start()

    async def cog_unload(self) -> None:
        self.reminder_loop.cancel()
        return await super().cog_unload()

    task = app_commands.Group(
        name="task",
        description="Command Group to create Tasks",
        guild_only=True
    )

    @task.command(name="user", description="Create a new User-Task")
    async def create_user(self, interaction: discord.Interaction):
        view = TaskView(self.bot, "user", user_id=interaction.user.id)
        await view.setup()
        view.message = await interaction.response.send_message(view=view)

    @task.command(name="guild", description="Create a new Guild-Task")
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def create_guild(self, interaction: discord.Interaction):
        view = TaskView(self.bot, "guild", guild_id=interaction.guild.id)
        await view.setup()
        view.message = await interaction.response.send_message(view=view)
        await self.bot.wait_until_ready()


    @tasks.loop(minutes=1)
    async def reminder_loop(self):
        now = datetime.now(pytz.timezone("Europe/Berlin"))
        today = now.date()

        try:
            async with self.bot.pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:

                    await cur.execute(
                        "SELECT userID, title, des, date FROM nexory_user_tasks "
                        "WHERE remindme=TRUE AND date<=%s",
                        (today,)
                    )
                    user_rows = await cur.fetchall()

                    for row in user_rows:
                        user = self.bot.get_user(row["userID"])
                        if user:
                            embed = discord.Embed(
                                title=f"`🔔` Task: {row['title']}",
                                description=row["des"],
                                color=discord.Color.blurple(),
                                timestamp=datetime.combine(row["date"], datetime.min.time())
                            )
                            embed.add_field(name="Date", value=str(row["date"]), inline=False)
                            embed.set_footer(text="Your Task Reminder")
                            try:
                                await user.send(embed=embed)
                            except Exception:
                                logger.warning(f"Konnte Reminder-DM an {row['userID']} nicht senden.")

                    if user_rows:
                        await cur.execute(
                            "DELETE FROM nexory_user_tasks WHERE remindme=TRUE AND date<=%s",
                            (today,)
                        )

                    await cur.execute(
                        "SELECT guildID, title, des, date FROM nexory_guild_tasks "
                        "WHERE remindme=TRUE AND date<=%s",
                        (today,)
                    )
                    guild_rows = await cur.fetchall()

                    for row in guild_rows:
                        guild = self.bot.get_guild(row["guildID"])
                        if not guild:
                            continue

                        await cur.execute(
                            "SELECT reminde_channel FROM nexory_guild_config WHERE guildID=%s",
                            (row["guildID"],)
                        )
                        config = await cur.fetchone()
                        channel_id = config["reminde_channel"] if config else None

                        channel = guild.get_channel(channel_id) if channel_id else None
                        if not channel or not channel.permissions_for(guild.me).send_messages:
                            channel = guild.system_channel
                        if not channel or not channel.permissions_for(guild.me).send_messages:
                            channel = next(
                                (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
                                None
                            )

                        if channel:
                            embed = discord.Embed(
                                title=f"`🔔` Task : {row['title']}",
                                description=row["des"],
                                color=discord.Color.green(),
                                timestamp=datetime.combine(row["date"], datetime.min.time())
                            )
                            embed.add_field(name="Date", value=str(row["date"]), inline=False)
                            embed.set_footer(text=f"Reminder for {guild.name}")
                            try:
                                await channel.send(embed=embed)
                            except Exception as e:
                                logger.warning(f"Konnte Reminder in Guild {row['guildID']} nicht senden: {e}")

                    if guild_rows:
                        await cur.execute(
                            "DELETE FROM nexory_guild_tasks WHERE remindme=TRUE AND date<=%s",
                            (today,)
                        )

                    await conn.commit()

        except Exception as e:
            logger.error(f"Fehler in reminder_loop: {e}")

    @reminder_loop.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()
        logger.info("Reminder loop startet... auf Aufgaben prüfen")

    
    @task.command(name="list", description="List all tasks for the user or guild")
    @commands.guild_only()
    async def list_tasks(self, interaction: discord.Interaction, scope: Literal["guild", "user"]):
        if scope == "user":
            table_name = "nexory_user_tasks"
            id_value = interaction.user.id
            id_field = "userID"
        else:
            table_name = "nexory_guild_tasks"
            id_value = interaction.guild.id
            id_field = "guildID"

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT title, des, date FROM {table_name} WHERE {id_field}=%s",
                    (id_value,)
                )
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message("No tasks found.", ephemeral=True)
            return

        view = TaskListView(rows, scope, interaction.user.id)
        await interaction.response.send_message(embed=view.get_embed(), view=view, ephemeral=True)


    @task.command(name="filter", description="Filter tasks by tag/status/user/priority")
    @commands.guild_only()
    async def filter_tasks(self, interaction: discord.Interaction, scope: Literal["guild", "user"], filter_by: Literal["tag", "status", "priority"], filter_value: str):
        if scope == "user":
            table_name = "nexory_user_tasks"
            id_value = interaction.user.id
            id_field = "userID"
        else:
            table_name = "nexory_guild_tasks"
            id_value = interaction.guild.id
            id_field = "guildID"

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT title, des, date FROM {table_name} WHERE {id_field}=%s AND {filter_by}=%s",
                    (id_value, filter_value)
                )
                rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message("No tasks found with that filter.", ephemeral=True)
            return

        message = ""
        for row in rows:
            title, des, date = row
            message += f"**{title}** - {des} ({date})\n"

        await interaction.response.send_message(message[:2000], ephemeral=True)


    @task.command(name="set_status", description="Set the status of a task (open/working/closed)")
    async def set_status(self, interaction: discord.Interaction, scope: Literal["guild", "user"], title: str, status: Literal["open", "working", "closed"]):
        if scope == "user":
            table_name = "nexory_user_tasks"
            id_value = interaction.user.id
            id_field = "userID"
        else:
            table_name = "nexory_guild_tasks"
            id_value = interaction.guild.id
            id_field = "guildID"

        async with self.bot.pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"UPDATE {table_name} SET status=%s WHERE {id_field}=%s AND title=%s",
                    (status, id_value, title)
                )
                await conn.commit()

        await interaction.response.send_message(f"Status of task '{title}' set to '{status}'.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(tasks(bot))
