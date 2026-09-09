"""
Dreams - Discord Bot
Studio: Kename Chou Games
Tipo: Terror
Presencia: › Dev: Supskevv!
"""

import os
import asyncio
import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv()

# ==================== CONFIG ====================
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dreams_bot")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN no está definido en las variables de entorno.")
if not MONGO_URI:
    raise ValueError("MONGO_URI no está definido en las variables de entorno.")

# ==================== FLASK KEEP-ALIVE (Render) ====================
app = Flask(__name__)

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dreams Bot | Online</title>
        <style>
            body {
                margin: 0;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #0a0a0a;
                color: #e0e0e0;
                font-family: 'Segoe UI', system-ui, sans-serif;
            }
            .card {
                background: #141414;
                border: 1px solid #2a2a2a;
                border-radius: 16px;
                padding: 2.5rem 3rem;
                text-align: center;
                box-shadow: 0 0 40px rgba(120, 0, 0, 0.15);
            }
            h1 { color: #c0392b; margin: 0 0 0.5rem; font-size: 2rem; }
            p { margin: 0.3rem 0; opacity: 0.85; }
            .status { color: #27ae60; font-weight: 600; }
            .footer { margin-top: 1.5rem; font-size: 0.85rem; opacity: 0.6; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Dreams</h1>
            <p>Kename Chou Games</p>
            <p class="status">● ONLINE</p>
            <p class="footer">Terror Bot • Render Keep-Alive</p>
        </div>
    </body>
    </html>
    """

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def start_keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()

# ==================== BOT SETUP ====================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(
    command_prefix="?",
    intents=intents,
    case_insensitive=True,
    help_command=None,
    activity=discord.CustomActivity(name="› Dev: Supskevv!")
)

# MongoDB
mongo_client: AsyncIOMotorClient = None
db = None

async def get_db():
    return db

# ==================== EVENTS ====================
@bot.event
async def on_ready():
    print(f"[READY] {bot.user} | ID: {bot.user.id}")
    print(f"[READY] Servidores: {len(bot.guilds)}")
    try:
        synced = await bot.tree.sync()
        print(f"[SYNC] {len(synced)} slash commands sincronizados.")
    except Exception as e:
        print(f"[ERROR SYNC] {e}")

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return

    if isinstance(error, commands.MissingRequiredArgument):
        cmd = ctx.command
        params = []
        for name, param in cmd.clean_params.items():
            if param.default is param.empty:
                params.append(f"<{name}>")
            else:
                params.append(f"[{name}]")
        usage = f"?{cmd.qualified_name} {' '.join(params)}"
        embed = discord.Embed(
            title="Uso incorrecto",
            description=f"**Uso correcto:**\n```{usage}```",
            color=0xC0392B
        )
        await ctx.send(embed=embed, delete_after=18)
        return

    if isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="Argumento inválido",
            description="Revisa el tipo de dato que estás enviando (usuario, número, duración, etc.).",
            color=0xC0392B
        )
        await ctx.send(embed=embed, delete_after=12)
        return

    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="Sin permisos",
            description="No tienes los permisos necesarios para usar este comando.",
            color=0xC0392B
        )
        await ctx.send(embed=embed, delete_after=10)
        return

    if isinstance(error, commands.BotMissingPermissions):
        embed = discord.Embed(
            title="Bot sin permisos",
            description="No tengo los permisos necesarios en este servidor.",
            color=0xC0392B
        )
        await ctx.send(embed=embed, delete_after=10)
        return

    if isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="Cooldown",
            description=f"Espera **{error.retry_after:.1f}s** antes de usar este comando de nuevo.",
            color=0xC0392B
        )
        await ctx.send(embed=embed, delete_after=8)
        return

    print(f"[ERROR] {ctx.command}: {error}")
    embed = discord.Embed(
        title="Error interno",
        description="Ocurrió un error inesperado.",
        color=0xC0392B
    )
    await ctx.send(embed=embed, delete_after=8)

@bot.event
async def on_member_join(member: discord.Member):
    from welcomes import handle_member_join
    await handle_member_join(member, db)

# ==================== MAIN ====================
async def main():
    global mongo_client, db

    start_keep_alive()

    mongo_client = AsyncIOMotorClient(MONGO_URI)
    db = mongo_client[DATABASE_NAME]

    try:
        await mongo_client.admin.command("ping")
        print("[MONGO] Conexión exitosa.")
    except Exception as e:
        print(f"[MONGO ERROR] {e}")
        raise

    import commands as cmd_module
    import welcomes as welcome_module

    await cmd_module.setup(bot, db)
    await welcome_module.setup(bot, db)

    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
