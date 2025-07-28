import discord
from discord.ext import commands
import os
import random
import string
from dotenv import load_dotenv

# Load environment
load_dotenv(dotenv_path=".env.dev")
TOKEN = os.getenv("DISCORD_TOKEN")
#MY_GUILD_ID = discord.Object(id=813092953236176928)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    #async def cleanup():
    #    test_guild = discord.Object(id=813092953236176928)  # Replace with your actual server ID

    #    try:
    #        bot.tree.clear_commands(guild=test_guild)  # ✅ no await here
    #        await bot.tree.sync(guild=test_guild)
    #        print("🧹 Cleared and resynced test guild commands.")
    #    except Exception as e:
    #        print(f"❌ Failed to clear commands: {e}")

    #await cleanup()

    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} slash commands.")
        for cmd in synced:
            print(f"   ↪️ /{cmd.name}")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")


# Utility: random group name and passphrase
def generate_listed_as(dungeon):
    suffix = ''.join(random.choices(string.ascii_lowercase, k=2))
    return f"{dungeon[:4].lower()}-{suffix}"

def generate_passphrase():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

# LFG command
@bot.tree.command(name="lfg", description="Create a Mythic+ group")
@discord.app_commands.describe(
    dungeon="Dungeon name (e.g., The Underrot)",
    key_level="Keystone level (e.g., 15)",
    timed="Was the dungeon previously timed?",
    your_role="Your role in the group",
    required_roles="Which roles you still need (e.g., tank, healer, dps)",
    listed_as="Optional name this group will be listed as"
)
async def lfg(
    interaction: discord.Interaction,
    dungeon: str,
    key_level: int,
    timed: bool,
    your_role: str,
    required_roles: str,
    listed_as: str = None
):
    listed_as = listed_as or generate_listed_as(dungeon)
    passphrase = generate_passphrase()

    embed = discord.Embed(
        title=f"Mythic+ Group: {dungeon} +{key_level}",
        description=(
            f"🔑 **Listed As**: `{listed_as}`\n"
            f"🧩 **Passphrase**: ||{passphrase}||\n"
            f"🏆 **Timed Before**: {'✅ Yes' if timed else '❌ No'}\n"
            f"🎮 **Creator's Role**: {your_role}\n"
            f"📌 **Needed Roles**: {required_roles}\n"
        ),
        color=discord.Color.dark_gold()
    )
    embed.set_footer(text="Click a role to join. Group expires in 30 minutes.")

    await interaction.response.send_message(embed=embed, view=LFGButtonView(), ephemeral=False)

# Role Button View
class LFGButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=1800)  # 30 minutes
        self.members = {"tank": [], "healer": [], "dps": []}

    @discord.ui.button(label="🛡 Tank", style=discord.ButtonStyle.primary)
    async def tank(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._join_role(interaction, "tank")

    @discord.ui.button(label="❤️ Healer", style=discord.ButtonStyle.success)
    async def healer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._join_role(interaction, "healer")

    @discord.ui.button(label="⚔️ DPS", style=discord.ButtonStyle.danger)
    async def dps(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._join_role(interaction, "dps")

    @discord.ui.button(label="⚙️ Manage", style=discord.ButtonStyle.secondary)
    async def manage(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ Coming soon: role switch / leave / cancel.", ephemeral=True)

    async def _join_role(self, interaction: discord.Interaction, role: str):
        user = interaction.user.name
        already_joined = any(user in users for users in self.members.values())

        if already_joined:
            await interaction.response.send_message("❗ You already joined a role.", ephemeral=True)
            return

        self.members[role].append(user)
        await interaction.response.send_message(f"✅ You joined as **{role.capitalize()}**!", ephemeral=True)

# Run bot
bot.run(TOKEN)

#@bot.tree.command(name="lfg", description="Create a Mythic+ group")
#async def lfg(interaction: discord.Interaction):
#    print(f"👋 /lfg triggered by {interaction.user}")
#    await interaction.response.send_message("✅ Global /lfg works!", ephemeral=True)