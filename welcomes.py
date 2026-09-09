"""
Sistema de bienvenidas - Dreams
"""

import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

COLOR_PRIMARY = 0xC0392B
COLOR_DARK = 0x1A1A1A

db: AsyncIOMotorDatabase = None
bot_ref: commands.Bot = None


async def get_welcome_config(guild_id: int) -> dict:
    doc = await db.guilds.find_one({"_id": guild_id})
    if not doc or "welcome" not in doc:
        return {
            "enabled": False,
            "channel_id": None,
            "message": "¡Bienvenido {user} a **{server}**!",
            "embed": True,
            "title": "Bienvenido",
            "description": "Esperamos que disfrutes tu estancia.",
            "color": COLOR_PRIMARY,
            "thumbnail": True,
            "image_url": None,
            "footer": "Dreams • Kename Chou Games",
            "dm_enabled": False,
            "dm_message": "¡Bienvenido a {server}!"
        }
    return doc["welcome"]


async def save_welcome_config(guild_id: int, config: dict):
    await db.guilds.update_one(
        {"_id": guild_id},
        {"$set": {"welcome": config}},
        upsert=True
    )


async def handle_member_join(member: discord.Member, database: AsyncIOMotorDatabase):
    global db
    db = database
    if member.bot:
        return

    config = await get_welcome_config(member.guild.id)
    if not config.get("enabled"):
        return

    channel_id = config.get("channel_id")
    if channel_id:
        channel = member.guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            content = (config.get("message") or "").replace("{user}", member.mention)\
                .replace("{server}", member.guild.name)\
                .replace("{membercount}", str(member.guild.member_count))

            if config.get("embed"):
                embed = discord.Embed(
                    title=config.get("title") or "Bienvenido",
                    description=(config.get("description") or "").replace("{user}", member.mention)\
                        .replace("{server}", member.guild.name)\
                        .replace("{membercount}", str(member.guild.member_count)),
                    color=config.get("color", COLOR_PRIMARY),
                    timestamp=datetime.now(timezone.utc)
                )
                if config.get("thumbnail"):
                    embed.set_thumbnail(url=member.display_avatar.url)
                if config.get("image_url"):
                    embed.set_image(url=config["image_url"])
                if config.get("footer"):
                    embed.set_footer(text=config["footer"])
                try:
                    await channel.send(content=content if content.strip() else None, embed=embed)
                except discord.Forbidden:
                    pass
            else:
                try:
                    await channel.send(content)
                except discord.Forbidden:
                    pass

    if config.get("dm_enabled"):
        dm_msg = (config.get("dm_message") or "").replace("{user}", member.name)\
            .replace("{server}", member.guild.name)
        try:
            await member.send(dm_msg)
        except (discord.Forbidden, discord.HTTPException):
            pass


# ==================== UI ====================
class WelcomeSetupView(discord.ui.View):
    def __init__(self, guild_id: int, config: dict):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    @discord.ui.button(label="Activar/Desactivar", style=discord.ButtonStyle.danger, row=0)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["enabled"] = not self.config.get("enabled", False)
        await save_welcome_config(self.guild_id, self.config)
        estado = "activo" if self.config["enabled"] else "desactivado"
        await interaction.response.send_message(f"Sistema de bienvenidas **{estado}**.", ephemeral=True)
        await self.refresh(interaction)

    @discord.ui.button(label="Canal", style=discord.ButtonStyle.secondary, row=0)
    async def set_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Menciona el canal o envía su ID. Tienes 60 segundos.",
            ephemeral=True
        )

        def check(m: discord.Message):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await bot_ref.wait_for("message", check=check, timeout=60)
            channel = None
            if msg.channel_mentions:
                channel = msg.channel_mentions[0]
            else:
                try:
                    channel = interaction.guild.get_channel(int(msg.content.strip()))
                except ValueError:
                    pass
            if channel and isinstance(channel, discord.TextChannel):
                self.config["channel_id"] = channel.id
                await save_welcome_config(self.guild_id, self.config)
                await msg.reply(f"Canal de bienvenidas: {channel.mention}", delete_after=8)
            else:
                await msg.reply("Canal no válido.", delete_after=8)
            try:
                await msg.delete()
            except Exception:
                pass
        except asyncio.TimeoutError:
            await interaction.followup.send("Tiempo agotado.", ephemeral=True)

    @discord.ui.button(label="Mensaje", style=discord.ButtonStyle.secondary, row=0)
    async def set_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageModal(self.config, self.guild_id, "message", "Mensaje de bienvenida")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Título", style=discord.ButtonStyle.secondary, row=1)
    async def set_title(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageModal(self.config, self.guild_id, "title", "Título del embed")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Descripción", style=discord.ButtonStyle.secondary, row=1)
    async def set_desc(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageModal(self.config, self.guild_id, "description", "Descripción del embed")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Imagen", style=discord.ButtonStyle.secondary, row=1)
    async def set_image(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageModal(self.config, self.guild_id, "image_url", "URL de imagen (vacío = quitar)")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Toggle Embed", style=discord.ButtonStyle.primary, row=2)
    async def toggle_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["embed"] = not self.config.get("embed", True)
        await save_welcome_config(self.guild_id, self.config)
        estado = "activado" if self.config["embed"] else "desactivado"
        await interaction.response.send_message(f"Embed **{estado}**.", ephemeral=True)

    @discord.ui.button(label="Toggle Thumbnail", style=discord.ButtonStyle.primary, row=2)
    async def toggle_thumb(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["thumbnail"] = not self.config.get("thumbnail", True)
        await save_welcome_config(self.guild_id, self.config)
        estado = "activado" if self.config["thumbnail"] else "desactivado"
        await interaction.response.send_message(f"Thumbnail **{estado}**.", ephemeral=True)

    @discord.ui.button(label="Toggle DM", style=discord.ButtonStyle.primary, row=2)
    async def toggle_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["dm_enabled"] = not self.config.get("dm_enabled", False)
        await save_welcome_config(self.guild_id, self.config)
        estado = "activado" if self.config["dm_enabled"] else "desactivado"
        await interaction.response.send_message(f"DM de bienvenida **{estado}**.", ephemeral=True)

    @discord.ui.button(label="Mensaje DM", style=discord.ButtonStyle.secondary, row=3)
    async def set_dm(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MessageModal(self.config, self.guild_id, "dm_message", "Mensaje de DM")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.danger, row=3)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Panel cerrado.", embed=None, view=None)
        self.stop()

    async def refresh(self, interaction: discord.Interaction):
        embed = build_welcome_embed(self.config)
        try:
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            pass


class MessageModal(discord.ui.Modal):
    def __init__(self, config: dict, guild_id: int, key: str, title: str):
        super().__init__(title=title[:45])
        self.config = config
        self.guild_id = guild_id
        self.key = key
        self.input = discord.ui.TextInput(
            label=title,
            style=discord.TextStyle.paragraph if key in ("message", "description", "dm_message") else discord.TextStyle.short,
            default=str(config.get(key) or ""),
            required=False,
            max_length=2000
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        value = self.input.value.strip()
        if self.key == "image_url" and not value:
            self.config[self.key] = None
        else:
            self.config[self.key] = value
        await save_welcome_config(self.guild_id, self.config)
        await interaction.response.send_message("Guardado correctamente.", ephemeral=True)


def build_welcome_embed(config: dict) -> discord.Embed:
    estado = "Activo" if config.get("enabled") else "Desactivado"
    canal = f"<#{config['channel_id']}>" if config.get("channel_id") else "`No configurado`"
    embed = discord.Embed(
        title="Configuración de Bienvenidas",
        description=f"**Estado:** {estado}\n**Canal:** {canal}",
        color=COLOR_PRIMARY,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Mensaje", value=f"```{(config.get('message') or '')[:120]}```", inline=False)
    embed.add_field(name="Embed", value="Sí" if config.get("embed") else "No", inline=True)
    embed.add_field(name="Thumbnail", value="Sí" if config.get("thumbnail") else "No", inline=True)
    embed.add_field(name="DM", value="Sí" if config.get("dm_enabled") else "No", inline=True)
    embed.add_field(name="Título", value=(config.get("title") or "—")[:50], inline=True)
    embed.add_field(name="Footer", value=(config.get("footer") or "—")[:40], inline=True)
    embed.set_footer(text="Usa los botones para configurar")
    return embed


@app_commands.command(name="welcome-setup", description="Configurar el sistema de bienvenidas")
@app_commands.checks.has_permissions(administrator=True)
async def welcome_setup(interaction: discord.Interaction):
    config = await get_welcome_config(interaction.guild.id)
    embed = build_welcome_embed(config)
    view = WelcomeSetupView(interaction.guild.id, config)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot, database: AsyncIOMotorDatabase):
    global db, bot_ref
    db = database
    bot_ref = bot
    bot.tree.add_command(welcome_setup)
    print("[WELCOMES] Módulo cargado.")
