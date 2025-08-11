from __future__ import annotations
import os
import discord
from dotenv import load_dotenv

# Decide which .env file to load (default to .env.dev for safety)
APP_ENV = os.getenv("APP_ENV", "dev").lower()
load_dotenv(dotenv_path=f".env.{APP_ENV}")  # loads .env.dev / .env.uat / .env.prod

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing. Put it in the selected .env file.")

# Optional
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Guilds to use for guild-scoped sync (for dev/uat quick command propagation)
GUILD_IDS = [int(x) for x in os.getenv("GUILD_IDS", "").split(",") if x.strip().isdigit()]

INTENTS = discord.Intents.default()
INTENTS.message_content = True