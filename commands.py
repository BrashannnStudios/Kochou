"""
Comandos de moderación + /bot-setup + /embed-create + ?cmds
Dreams - Kename Chou Games
"""

import re
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, Union

COLOR_PRIMARY = 0xC0392B
COLOR_SUCCESS = 0x27AE60
COLOR_WARN = 0xF39C12
COLOR_DARK = 0x1A1A1A

db: AsyncIOMotorDatabase = None
bot_ref: commands.Bot = None


# ==================== HELPERS ====================
async def get_guild_config(guild_id: int) -> dict:
    doc = await db.guilds.find_one({"_id": guild_id})
    if not doc:
        return {
            "mod_log": None,
            "staff_roles": [],
            "admin_roles": [],
            "mute_role": None
        }
    return {
        "mod_log": doc.get("mod_log"),
        "staff_roles": doc.get("staff_roles", []),
        "admin_roles": doc.get("admin_roles", []),
        "mute_role": doc.get("mute_role")
    }


async def save_guild_config(guild_id: int, data: dict):
    await db.guilds.update_one({"_id": guild_id}, {"$set": data}, upsert=True)


async def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    config = await get_guild_config(member.guild.id)
    roles = set(config.get("staff_roles", []) + config.get("admin_roles", []))
    return any(r.id in roles for r in member.roles)


async def send_mod_log(guild: discord.Guild, embed: discord.Embed):
    config = await get_guild_config(guild.id)
    if not config.get("mod_log"):
        return
    channel = guild.get_channel(config["mod_log"])
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def notify_user(user: Union[discord.Member, discord.User], action: str, reason: str, guild: discord.Guild, moderator: discord.Member, duration: str = None):
    """Envía notificación por DM. No se usa en notas."""
    embed = discord.Embed(
        title=action,
        color=COLOR_PRIMARY,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Servidor", value=guild.name, inline=True)
    embed.add_field(name="Moderador", value=str(moderator), inline=True)
    if duration:
        embed.add_field(name="Duración", value=duration, inline=True)
    embed.add_field(name="Razón", value=reason or "Sin razón especificada", inline=False)
    embed.set_footer(text="Dreams • Kename Chou Games")
    try:
        await user.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass


def parse_duration(text: str) -> Optional[timedelta]:
    if not text:
        return None
    match = re.fullmatch(r"(\d+)([smhdw])", text.lower().strip())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    mapping = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days", "w": "weeks"}
    return timedelta(**{mapping[unit]: value})


# ==================== /bot-setup ====================
class BotSetupView(discord.ui.View):
    def __init__(self, guild_id: int, config: dict):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.config = config

    @discord.ui.button(label="Canal de Logs", style=discord.ButtonStyle.secondary, row=0)
    async def set_log(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Menciona el canal o envía su ID. Tienes 60 segundos.",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await bot_ref.wait_for("message", check=check, timeout=60)
            channel = None
            if msg.channel_mentions:
                channel = msg.channel_mentions[0]
            else:
                try:
                    channel = interaction.guild.get_channel(int(msg.content.strip()))
                except Exception:
                    pass
            if channel and isinstance(channel, discord.TextChannel):
                self.config["mod_log"] = channel.id
                await save_guild_config(self.guild_id, {"mod_log": channel.id})
                await msg.reply(f"Canal de logs configurado: {channel.mention}", delete_after=8)
            else:
                await msg.reply("Canal no válido.", delete_after=8)
            try:
                await msg.delete()
            except Exception:
                pass
        except asyncio.TimeoutError:
            await interaction.followup.send("Tiempo agotado.", ephemeral=True)

    @discord.ui.button(label="Roles Staff", style=discord.ButtonStyle.secondary, row=0)
    async def set_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Menciona los roles de staff. Escribe `clear` para eliminarlos.",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await bot_ref.wait_for("message", check=check, timeout=60)
            if msg.content.lower().strip() == "clear":
                self.config["staff_roles"] = []
                await save_guild_config(self.guild_id, {"staff_roles": []})
                await msg.reply("Roles de staff eliminados.", delete_after=8)
            else:
                roles = msg.role_mentions
                if roles:
                    ids = [r.id for r in roles]
                    self.config["staff_roles"] = ids
                    await save_guild_config(self.guild_id, {"staff_roles": ids})
                    names = ", ".join(r.mention for r in roles)
                    await msg.reply(f"Roles de staff actualizados: {names}", delete_after=10)
                else:
                    await msg.reply("No se detectaron roles.", delete_after=8)
            try:
                await msg.delete()
            except Exception:
                pass
        except asyncio.TimeoutError:
            await interaction.followup.send("Tiempo agotado.", ephemeral=True)

    @discord.ui.button(label="Roles Admin", style=discord.ButtonStyle.secondary, row=0)
    async def set_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Menciona los roles de administrador. Escribe `clear` para eliminarlos.",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await bot_ref.wait_for("message", check=check, timeout=60)
            if msg.content.lower().strip() == "clear":
                self.config["admin_roles"] = []
                await save_guild_config(self.guild_id, {"admin_roles": []})
                await msg.reply("Roles de administrador eliminados.", delete_after=8)
            else:
                roles = msg.role_mentions
                if roles:
                    ids = [r.id for r in roles]
                    self.config["admin_roles"] = ids
                    await save_guild_config(self.guild_id, {"admin_roles": ids})
                    names = ", ".join(r.mention for r in roles)
                    await msg.reply(f"Roles de administrador actualizados: {names}", delete_after=10)
                else:
                    await msg.reply("No se detectaron roles.", delete_after=8)
            try:
                await msg.delete()
            except Exception:
                pass
        except asyncio.TimeoutError:
            await interaction.followup.send("Tiempo agotado.", ephemeral=True)

    @discord.ui.button(label="Rol Mute", style=discord.ButtonStyle.secondary, row=1)
    async def set_mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Menciona el rol de mute o escribe `clear` para eliminarlo.",
            ephemeral=True
        )

        def check(m):
            return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id

        try:
            msg = await bot_ref.wait_for("message", check=check, timeout=60)
            if msg.content.lower().strip() == "clear":
                self.config["mute_role"] = None
                await save_guild_config(self.guild_id, {"mute_role": None})
                await msg.reply("Rol de mute eliminado.", delete_after=8)
            else:
                role = msg.role_mentions[0] if msg.role_mentions else None
                if not role:
                    try:
                        role = interaction.guild.get_role(int(msg.content.strip()))
                    except Exception:
                        pass
                if role:
                    self.config["mute_role"] = role.id
                    await save_guild_config(self.guild_id, {"mute_role": role.id})
                    await msg.reply(f"Rol de mute configurado: {role.mention}", delete_after=8)
                else:
                    await msg.reply("Rol no válido.", delete_after=8)
            try:
                await msg.delete()
            except Exception:
                pass
        except asyncio.TimeoutError:
            await interaction.followup.send("Tiempo agotado.", ephemeral=True)

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.danger, row=1)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Panel cerrado.", embed=None, view=None)
        self.stop()


def build_bot_setup_embed(config: dict, guild: discord.Guild) -> discord.Embed:
    log_ch = f"<#{config['mod_log']}>" if config.get("mod_log") else "`No configurado`"
    staff = ", ".join(f"<@&{r}>" for r in config.get("staff_roles", [])) or "`Ninguno`"
    admin = ", ".join(f"<@&{r}>" for r in config.get("admin_roles", [])) or "`Ninguno`"
    mute = f"<@&{config['mute_role']}>" if config.get("mute_role") else "`No configurado`"

    embed = discord.Embed(
        title="Configuración del Bot",
        description="Configura los logs de moderación, roles de staff y administrador.",
        color=COLOR_PRIMARY,
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Canal de Logs", value=log_ch, inline=False)
    embed.add_field(name="Roles Staff", value=staff[:1000], inline=False)
    embed.add_field(name="Roles Admin", value=admin[:1000], inline=False)
    embed.add_field(name="Rol Mute", value=mute, inline=False)
    embed.set_footer(text="Dreams • Kename Chou Games")
    return embed


@app_commands.command(name="bot-setup", description="Configurar logs, roles de staff/admin y mute")
@app_commands.checks.has_permissions(administrator=True)
async def bot_setup(interaction: discord.Interaction):
    config = await get_guild_config(interaction.guild.id)
    embed = build_bot_setup_embed(config, interaction.guild)
    view = BotSetupView(interaction.guild.id, config)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


# ==================== /embed-create ====================
class EmbedCreateModal(discord.ui.Modal, title="Crear Embed"):
    def __init__(self):
        super().__init__()
        self.title_input = discord.ui.TextInput(label="Título", required=False, max_length=256)
        self.desc_input = discord.ui.TextInput(label="Descripción", style=discord.TextStyle.paragraph, required=False, max_length=4000)
        self.color_input = discord.ui.TextInput(label="Color (hex)", required=False, max_length=7, default="#C0392B")
        self.footer_input = discord.ui.TextInput(label="Footer", required=False, max_length=2048)
        self.image_input = discord.ui.TextInput(label="URL de imagen", required=False, max_length=500)
        self.add_item(self.title_input)
        self.add_item(self.desc_input)
        self.add_item(self.color_input)
        self.add_item(self.footer_input)
        self.add_item(self.image_input)

    async def on_submit(self, interaction: discord.Interaction):
        color = COLOR_PRIMARY
        if self.color_input.value:
            try:
                color = int(self.color_input.value.strip().lstrip("#"), 16)
            except ValueError:
                pass

        embed = discord.Embed(
            title=self.title_input.value or None,
            description=self.desc_input.value or None,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        if self.footer_input.value:
            embed.set_footer(text=self.footer_input.value)
        if self.image_input.value:
            embed.set_image(url=self.image_input.value)

        await interaction.response.send_message(embed=embed)


@app_commands.command(name="embed-create", description="Crear un embed personalizado")
@app_commands.checks.has_permissions(manage_messages=True)
async def embed_create(interaction: discord.Interaction):
    await interaction.response.send_modal(EmbedCreateModal())


# ==================== PREFIX COMMANDS ====================
@commands.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def lock(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    if overwrite.send_messages is False:
        await ctx.send(embed=discord.Embed(description="Este canal ya está bloqueado.", color=COLOR_WARN), delete_after=8)
        return
    overwrite.send_messages = False
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(description=f"🔒 Canal {channel.mention} bloqueado.", color=COLOR_SUCCESS))

    log = discord.Embed(title="Canal bloqueado", color=COLOR_PRIMARY, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Canal", value=channel.mention)
    log.add_field(name="Moderador", value=ctx.author.mention)
    await send_mod_log(ctx.guild, log)


@commands.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
    channel = channel or ctx.channel
    overwrite = channel.overwrites_for(ctx.guild.default_role)
    if overwrite.send_messages is not False:
        await ctx.send(embed=discord.Embed(description="Este canal no está bloqueado.", color=COLOR_WARN), delete_after=8)
        return
    overwrite.send_messages = None
    await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send(embed=discord.Embed(description=f"🔓 Canal {channel.mention} desbloqueado.", color=COLOR_SUCCESS))

    log = discord.Embed(title="Canal desbloqueado", color=COLOR_SUCCESS, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Canal", value=channel.mention)
    log.add_field(name="Moderador", value=ctx.author.mention)
    await send_mod_log(ctx.guild, log)


@commands.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx: commands.Context, member: discord.Member, *, reason: str = "Sin razón"):
    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send(embed=discord.Embed(description="No puedes banear a alguien con un rol igual o superior al tuyo.", color=COLOR_PRIMARY), delete_after=10)
        return
    if member == ctx.author or member == ctx.guild.me:
        await ctx.send(embed=discord.Embed(description="Acción no permitida.", color=COLOR_PRIMARY), delete_after=8)
        return

    await notify_user(member, "Has sido baneado", reason, ctx.guild, ctx.author)
    await member.ban(reason=f"{ctx.author}: {reason}")
    await ctx.send(embed=discord.Embed(description=f"**{member}** ha sido baneado.\nRazón: {reason}", color=COLOR_PRIMARY))

    log = discord.Embed(title="Usuario baneado", color=COLOR_PRIMARY, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Usuario", value=f"{member} (`{member.id}`)")
    log.add_field(name="Moderador", value=ctx.author.mention)
    log.add_field(name="Razón", value=reason, inline=False)
    await send_mod_log(ctx.guild, log)


@commands.command(name="unban")
@commands.has_permissions(ban_members=True)
async def unban(ctx: commands.Context, user: str, *, reason: str = "Sin razón"):
    banned = [entry async for entry in ctx.guild.bans(limit=None)]
    target = None
    for entry in banned:
        if str(entry.user.id) == user or str(entry.user) == user or entry.user.name.lower() == user.lower():
            target = entry.user
            break
    if not target:
        await ctx.send(embed=discord.Embed(description="Usuario no encontrado en la lista de baneos.", color=COLOR_PRIMARY), delete_after=10)
        return

    await ctx.guild.unban(target, reason=f"{ctx.author}: {reason}")
    await ctx.send(embed=discord.Embed(description=f"**{target}** ha sido desbaneado.", color=COLOR_SUCCESS))

    log = discord.Embed(title="Usuario desbaneado", color=COLOR_SUCCESS, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Usuario", value=f"{target} (`{target.id}`)")
    log.add_field(name="Moderador", value=ctx.author.mention)
    log.add_field(name="Razón", value=reason, inline=False)
    await send_mod_log(ctx.guild, log)


@commands.command(name="tempban")
@commands.has_permissions(ban_members=True)
async def tempban(ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = "Sin razón"):
    delta = parse_duration(duration)
    if not delta:
        await ctx.send(embed=discord.Embed(
            title="Uso incorrecto",
            description="**Uso correcto:**\n```?tempban <usuario> <duración> [razón]\nEjemplo: ?tempban @usuario 2h spam```",
            color=COLOR_PRIMARY
        ), delete_after=15)
        return

    if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
        await ctx.send(embed=discord.Embed(description="No puedes banear a alguien con un rol igual o superior al tuyo.", color=COLOR_PRIMARY), delete_after=10)
        return

    await notify_user(member, "Has sido baneado temporalmente", reason, ctx.guild, ctx.author, duration)
    await member.ban(reason=f"{ctx.author}: {reason} | {duration}")
    await ctx.send(embed=discord.Embed(description=f"**{member}** ha sido baneado por **{duration}**.\nRazón: {reason}", color=COLOR_PRIMARY))

    log = discord.Embed(title="Ban temporal", color=COLOR_PRIMARY, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Usuario", value=f"{member} (`{member.id}`)")
    log.add_field(name="Duración", value=duration)
    log.add_field(name="Moderador", value=ctx.author.mention)
    log.add_field(name="Razón", value=reason, inline=False)
    await send_mod_log(ctx.guild, log)

    async def unban_later():
        await asyncio.sleep(delta.total_seconds())
        try:
            await ctx.guild.unban(member, reason="Ban temporal finalizado")
            log2 = discord.Embed(title="Ban temporal finalizado", color=COLOR_SUCCESS, timestamp=datetime.now(timezone.utc))
            log2.add_field(name="Usuario", value=f"{member} (`{member.id}`)")
            await send_mod_log(ctx.guild, log2)
        except Exception:
            pass

    bot_ref.loop.create_task(unban_later())


@commands.command(name="warn")
@commands.has_permissions(moderate_members=True)
async def warn(ctx: commands.Context, member: discord.Member, *, reason: str = "Sin razón"):
    if member.bot or member == ctx.author:
        await ctx.send(embed=discord.Embed(description="No puedes warnear a ese usuario.", color=COLOR_PRIMARY), delete_after=8)
        return

    warn_doc = {
        "reason": reason,
        "moderator_id": ctx.author.id,
        "moderator_name": str(ctx.author),
        "timestamp": datetime.now(timezone.utc)
    }
    await db.warnings.update_one(
        {"guild_id": ctx.guild.id, "user_id": member.id},
        {"$push": {"warns": warn_doc}},
        upsert=True
    )

    await notify_user(member, "Has recibido una advertencia", reason, ctx.guild, ctx.author)

    total = await db.warnings.find_one({"guild_id": ctx.guild.id, "user_id": member.id})
    count = len(total.get("warns", [])) if total else 1

    await ctx.send(embed=discord.Embed(
        description=f"**{member}** ha recibido una advertencia.\nRazón: {reason}\nTotal: **{count}**",
        color=COLOR_WARN
    ))

    log = discord.Embed(title="Advertencia", color=COLOR_WARN, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Usuario", value=f"{member} (`{member.id}`)")
    log.add_field(name="Moderador", value=ctx.author.mention)
    log.add_field(name="Razón", value=reason, inline=False)
    log.add_field(name="Total", value=str(count))
    await send_mod_log(ctx.guild, log)


@commands.command(name="delwarn")
@commands.has_permissions(moderate_members=True)
async def delwarn(ctx: commands.Context, member: discord.Member, index: int = 1):
    doc = await db.warnings.find_one({"guild_id": ctx.guild.id, "user_id": member.id})
    if not doc or not doc.get("warns"):
        await ctx.send(embed=discord.Embed(description="Este usuario no tiene advertencias.", color=COLOR_WARN), delete_after=8)
        return
    warns = doc["warns"]
    if index < 1 or index > len(warns):
        await ctx.send(embed=discord.Embed(description=f"Índice inválido. Tiene {len(warns)} advertencias.", color=COLOR_PRIMARY), delete_after=10)
        return
    removed = warns.pop(index - 1)
    await db.warnings.update_one(
        {"guild_id": ctx.guild.id, "user_id": member.id},
        {"$set": {"warns": warns}}
    )
    await ctx.send(embed=discord.Embed(
        description=f"Advertencia #{index} eliminada de **{member}**.\nRazón original: {removed.get('reason')}",
        color=COLOR_SUCCESS
    ))


@commands.command(name="warnings")
@commands.has_permissions(moderate_members=True)
async def warnings(ctx: commands.Context, member: discord.Member):
    doc = await db.warnings.find_one({"guild_id": ctx.guild.id, "user_id": member.id})
    if not doc or not doc.get("warns"):
        await ctx.send(embed=discord.Embed(description=f"**{member}** no tiene advertencias.", color=COLOR_SUCCESS), delete_after=10)
        return

    embed = discord.Embed(title=f"Advertencias de {member}", color=COLOR_WARN, timestamp=datetime.now(timezone.utc))
    for i, w in enumerate(doc["warns"], 1):
        ts = w.get("timestamp")
        ts_str = ts.strftime("%d/%m/%Y %H:%M") if isinstance(ts, datetime) else "—"
        embed.add_field(
            name=f"#{i} • {w.get('moderator_name', 'Desconocido')}",
            value=f"{w.get('reason', 'Sin razón')}\n`{ts_str}`",
            inline=False
        )
    embed.set_footer(text=f"Total: {len(doc['warns'])}")
    await ctx.send(embed=embed)


@commands.command(name="noteadd")
@commands.has_permissions(moderate_members=True)
async def noteadd(ctx: commands.Context, member: discord.Member, *, note: str):
    note_doc = {
        "note": note,
        "moderator_id": ctx.author.id,
        "moderator_name": str(ctx.author),
        "timestamp": datetime.now(timezone.utc)
    }
    await db.notes.update_one(
        {"guild_id": ctx.guild.id, "user_id": member.id},
        {"$push": {"notes": note_doc}},
        upsert=True
    )
    await ctx.send(embed=discord.Embed(description=f"Nota añadida a **{member}**.", color=COLOR_SUCCESS), delete_after=8)


@commands.command(name="noteremove")
@commands.has_permissions(moderate_members=True)
async def noteremove(ctx: commands.Context, member: discord.Member, index: int = 1):
    doc = await db.notes.find_one({"guild_id": ctx.guild.id, "user_id": member.id})
    if not doc or not doc.get("notes"):
        await ctx.send(embed=discord.Embed(description="Este usuario no tiene notas.", color=COLOR_WARN), delete_after=8)
        return
    notes = doc["notes"]
    if index < 1 or index > len(notes):
        await ctx.send(embed=discord.Embed(description=f"Índice inválido. Tiene {len(notes)} notas.", color=COLOR_PRIMARY), delete_after=10)
        return
    notes.pop(index - 1)
    await db.notes.update_one(
        {"guild_id": ctx.guild.id, "user_id": member.id},
        {"$set": {"notes": notes}}
    )
    await ctx.send(embed=discord.Embed(description=f"Nota #{index} eliminada de **{member}**.", color=COLOR_SUCCESS), delete_after=8)


@commands.command(name="viewnotes")
@commands.has_permissions(moderate_members=True)
async def viewnotes(ctx: commands.Context, member: discord.Member):
    doc = await db.notes.find_one({"guild_id": ctx.guild.id, "user_id": member.id})
    if not doc or not doc.get("notes"):
        await ctx.send(embed=discord.Embed(description=f"**{member}** no tiene notas.", color=COLOR_SUCCESS), delete_after=10)
        return

    embed = discord.Embed(title=f"Notas de {member}", color=COLOR_DARK, timestamp=datetime.now(timezone.utc))
    for i, n in enumerate(doc["notes"], 1):
        ts = n.get("timestamp")
        ts_str = ts.strftime("%d/%m/%Y %H:%M") if isinstance(ts, datetime) else "—"
        embed.add_field(
            name=f"#{i} • {n.get('moderator_name', 'Desconocido')}",
            value=f"{n.get('note', '')}\n`{ts_str}`",
            inline=False
        )
    embed.set_footer(text=f"Total: {len(doc['notes'])} • Solo visible para el staff")
    await ctx.send(embed=embed)


@commands.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx: commands.Context, member: discord.Member, duration: Optional[str] = None, *, reason: str = "Sin razón"):
    config = await get_guild_config(ctx.guild.id)
    mute_role_id = config.get("mute_role")
    if not mute_role_id:
        await ctx.send(embed=discord.Embed(
            description="No hay un rol de mute configurado. Usa `/bot-setup`.",
            color=COLOR_PRIMARY
        ), delete_after=12)
        return

    mute_role = ctx.guild.get_role(mute_role_id)
    if not mute_role:
        await ctx.send(embed=discord.Embed(description="El rol de mute configurado ya no existe.", color=COLOR_PRIMARY), delete_after=10)
        return

    if mute_role in member.roles:
        await ctx.send(embed=discord.Embed(description="Este usuario ya está muteado.", color=COLOR_WARN), delete_after=8)
        return

    delta = parse_duration(duration) if duration else None
    await member.add_roles(mute_role, reason=f"{ctx.author}: {reason}")
    await notify_user(member, "Has sido muteado", reason, ctx.guild, ctx.author, duration)

    text = f"**{member}** ha sido muteado."
    if duration:
        text += f"\nDuración: **{duration}**"
    text += f"\nRazón: {reason}"
    await ctx.send(embed=discord.Embed(description=text, color=COLOR_PRIMARY))

    log = discord.Embed(title="Usuario muteado", color=COLOR_PRIMARY, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Usuario", value=f"{member} (`{member.id}`)")
    log.add_field(name="Moderador", value=ctx.author.mention)
    if duration:
        log.add_field(name="Duración", value=duration)
    log.add_field(name="Razón", value=reason, inline=False)
    await send_mod_log(ctx.guild, log)

    if delta:
        async def unmute_later():
            await asyncio.sleep(delta.total_seconds())
            try:
                if mute_role in member.roles:
                    await member.remove_roles(mute_role, reason="Mute temporal finalizado")
                    log2 = discord.Embed(title="Mute temporal finalizado", color=COLOR_SUCCESS, timestamp=datetime.now(timezone.utc))
                    log2.add_field(name="Usuario", value=f"{member} (`{member.id}`)")
                    await send_mod_log(ctx.guild, log2)
            except Exception:
                pass
        bot_ref.loop.create_task(unmute_later())


@commands.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx: commands.Context, member: discord.Member, *, reason: str = "Sin razón"):
    config = await get_guild_config(ctx.guild.id)
    mute_role_id = config.get("mute_role")
    if not mute_role_id:
        await ctx.send(embed=discord.Embed(description="No hay un rol de mute configurado.", color=COLOR_PRIMARY), delete_after=10)
        return
    mute_role = ctx.guild.get_role(mute_role_id)
    if not mute_role or mute_role not in member.roles:
        await ctx.send(embed=discord.Embed(description="Este usuario no está muteado.", color=COLOR_WARN), delete_after=8)
        return

    await member.remove_roles(mute_role, reason=f"{ctx.author}: {reason}")
    await ctx.send(embed=discord.Embed(description=f"**{member}** ha sido desmuteado.", color=COLOR_SUCCESS))

    log = discord.Embed(title="Usuario desmuteado", color=COLOR_SUCCESS, timestamp=datetime.now(timezone.utc))
    log.add_field(name="Usuario", value=f"{member} (`{member.id}`)")
    log.add_field(name="Moderador", value=ctx.author.mention)
    log.add_field(name="Razón", value=reason, inline=False)
    await send_mod_log(ctx.guild, log)


@commands.command(name="slowmode")
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx: commands.Context, seconds: int = 0, channel: Optional[discord.TextChannel] = None):
    channel = channel or ctx.channel
    if seconds < 0 or seconds > 21600:
        await ctx.send(embed=discord.Embed(
            title="Uso incorrecto",
            description="**Uso correcto:**\n```?slowmode <segundos> [canal]\nRango: 0-21600```",
            color=COLOR_PRIMARY
        ), delete_after=12)
        return
    await channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await ctx.send(embed=discord.Embed(description=f"Slowmode desactivado en {channel.mention}.", color=COLOR_SUCCESS))
    else:
        await ctx.send(embed=discord.Embed(description=f"Slowmode de **{seconds}s** activado en {channel.mention}.", color=COLOR_SUCCESS))


@commands.command(name="dm")
@commands.has_permissions(moderate_members=True)
async def dm(ctx: commands.Context, member: discord.Member, *, message: str):
    try:
        embed = discord.Embed(
            title=f"Mensaje de {ctx.guild.name}",
            description=message,
            color=COLOR_PRIMARY,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Enviado por el staff • Dreams")
        await member.send(embed=embed)
        await ctx.send(embed=discord.Embed(description=f"Mensaje enviado a **{member}**.", color=COLOR_SUCCESS), delete_after=8)
    except (discord.Forbidden, discord.HTTPException):
        await ctx.send(embed=discord.Embed(description="No se pudo enviar el mensaje. El usuario tiene los DMs cerrados o bloqueó al bot.", color=COLOR_PRIMARY), delete_after=10)


@commands.command(name="userinfo")
async def userinfo(ctx: commands.Context, member: Optional[discord.Member] = None):
    member = member or ctx.author
    roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
    roles_str = ", ".join(roles[:15]) + ("..." if len(roles) > 15 else "") or "Ninguno"

    embed = discord.Embed(title=f"Información de {member}", color=member.color or COLOR_PRIMARY, timestamp=datetime.now(timezone.utc))
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
    embed.add_field(name="Apodo", value=member.nick or "Ninguno", inline=True)
    embed.add_field(name="Bot", value="Sí" if member.bot else "No", inline=True)
    embed.add_field(name="Cuenta creada", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
    embed.add_field(name="Se unió", value=discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "N/A", inline=True)
    embed.add_field(name=f"Roles [{len(roles)}]", value=roles_str, inline=False)
    embed.set_footer(text="Dreams • Kename Chou Games")
    await ctx.send(embed=embed)


@commands.command(name="serverinfo")
async def serverinfo(ctx: commands.Context):
    g = ctx.guild
    embed = discord.Embed(title=g.name, color=COLOR_PRIMARY, timestamp=datetime.now(timezone.utc))
    if g.icon:
        embed.set_thumbnail(url=g.icon.url)
    embed.add_field(name="ID", value=f"`{g.id}`", inline=True)
    embed.add_field(name="Dueño", value=str(g.owner), inline=True)
    embed.add_field(name="Creado", value=discord.utils.format_dt(g.created_at, "R"), inline=True)
    embed.add_field(name="Miembros", value=str(g.member_count), inline=True)
    embed.add_field(name="Canales", value=str(len(g.channels)), inline=True)
    embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
    embed.add_field(name="Boosts", value=f"Nivel {g.premium_tier} ({g.premium_subscription_count})", inline=True)
    embed.set_footer(text="Dreams • Kename Chou Games")
    await ctx.send(embed=embed)


@commands.command(name="cmds")
async def cmds(ctx: commands.Context):
    embed = discord.Embed(
        title="Comandos de Dreams",
        description="**Prefix:** `?`  •  **Slash:** `/`\nLos comandos con prefix no distinguen mayúsculas.",
        color=COLOR_PRIMARY,
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(
        name="Slash Commands",
        value=(
            "`/welcome-setup` — Configurar bienvenidas\n"
            "`/bot-setup` — Logs, roles staff/admin, mute\n"
            "`/embed-create` — Crear embeds personalizados"
        ),
        inline=True
    )

    embed.add_field(
        name="Moderación",
        value=(
            "`?lock` `[canal]` — Bloquear canal\n"
            "`?unlock` `[canal]` — Desbloquear canal\n"
            "`?ban` `<user>` `[razón]` — Ban permanente\n"
            "`?unban` `<id/nombre>` — Desbanear\n"
            "`?tempban` `<user>` `<tiempo>` — Ban temporal\n"
            "`?mute` `<user>` `[tiempo]` — Mutear\n"
            "`?unmute` `<user>` — Desmutear\n"
            "`?slowmode` `<seg>` `[canal]` — Slowmode"
        ),
        inline=True
    )

    embed.add_field(
        name="Warns y Notas",
        value=(
            "`?warn` `<user>` `[razón]` — Advertir\n"
            "`?delwarn` `<user>` `[índice]` — Eliminar warn\n"
            "`?warnings` `<user>` — Ver warns\n"
            "`?noteadd` `<user>` `<texto>` — Añadir nota\n"
            "`?noteremove` `<user>` `[índice]` — Eliminar nota\n"
            "`?viewnotes` `<user>` — Ver notas"
        ),
        inline=True
    )

    embed.add_field(
        name="Utilidad",
        value=(
            "`?dm` `<user>` `<mensaje>` — Enviar DM\n"
            "`?userinfo` `[user]` — Info de usuario\n"
            "`?serverinfo` — Info del servidor\n"
            "`?cmds` — Este panel"
        ),
        inline=True
    )

    embed.add_field(
        name="Notas",
        value=(
            "• Duraciones: `30s` `10m` `2h` `1d` `1w`\n"
            "• Las notas son internas y **no** se notifican al usuario\n"
            "• Warns, bans y mutes **sí** se notifican por DM"
        ),
        inline=False
    )

    embed.set_footer(text="Dreams • Kename Chou Games")
    await ctx.send(embed=embed)


# ==================== SETUP ====================
async def setup(bot: commands.Bot, database: AsyncIOMotorDatabase):
    global db, bot_ref
    db = database
    bot_ref = bot

    bot.tree.add_command(bot_setup)
    bot.tree.add_command(embed_create)

    bot.add_command(lock)
    bot.add_command(unlock)
    bot.add_command(ban)
    bot.add_command(unban)
    bot.add_command(tempban)
    bot.add_command(warn)
    bot.add_command(delwarn)
    bot.add_command(warnings)
    bot.add_command(noteadd)
    bot.add_command(noteremove)
    bot.add_command(viewnotes)
    bot.add_command(mute)
    bot.add_command(unmute)
    bot.add_command(slowmode)
    bot.add_command(dm)
    bot.add_command(userinfo)
    bot.add_command(serverinfo)
    bot.add_command(cmds)

    print("[COMMANDS] Módulo cargado.")
