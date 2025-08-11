# bot.py
# -----------------------
# PartyCrusher — Mythic+ LFG Discord bot
# Single-file, clean structure with comments and modern discord.py (2.x) features.
# -----------------------

from __future__ import annotations

import os
import random
import string
from typing import Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import find
from dotenv import load_dotenv, dotenv_values
from pathlib import Path

#ENV_FILE = ".env.prod"
#ENV_PATH = Path(__file__).resolve().parent / ENV_FILE

#print("ENV DEBUG →")
#print("  path:", ENV_PATH)
#print("  exists:", ENV_PATH.exists())
#print("  cwd:", Path.cwd())
#print("  files here:", [p.name for p in ENV_PATH.parent.iterdir()])

# Read raw contents (mask token if present)
#if ENV_PATH.exists():
#    raw = ENV_PATH.read_text(encoding="utf-8", errors="replace")
#    print("  first 200 chars:", raw[:200].replace(os.getenv("DISCORD_TOKEN", ""), "***"))

#vals = dotenv_values(str(ENV_PATH), encoding="utf-8")
#print("  parsed keys:", list(vals.keys()))

# Now actually load it (force override just in case something is set in your shell)
#load_dotenv(dotenv_path=str(ENV_PATH), override=True, encoding="utf-8")

#print("  DISCORD_TOKEN present after load?:", bool(os.getenv("DISCORD_TOKEN")))

# =========================
# Environment / Constants
# =========================

# Load variables from .env.dev (DISCORD_TOKEN required)
#load_dotenv(dotenv_path=".env.prod")
#TOKEN = os.getenv("DISCORD_TOKEN")
#if not TOKEN:
#    raise RuntimeError("DISCORD_TOKEN is missing. Add it to .env.dev")

# --- env loader ---

APP_ENV = os.getenv("APP_ENV", "prod").lower()  # dev | qa | prod
ENV_PATH = Path(__file__).resolve().parent / f".env.{APP_ENV}"

# Works both locally and in Docker (compose mounts the env file)
if ENV_PATH.exists():
    load_dotenv(dotenv_path=str(ENV_PATH), override=True)

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError(f"DISCORD_TOKEN is missing (looked in {ENV_PATH.name} and process env)")
# --- end env loader ---

# Canonical display names used in UI and per-guild role resolution
ROLE_TITLES = ["Tank", "Healer", "Melee DPS", "Ranged DPS"]

# Internal role keys -> display titles
ROLE_KEY_TO_TITLE = {
    "tank": "Tank",
    "healer": "Healer",
    "meleedps": "Melee DPS",
    "rangeddps": "Ranged DPS",
}

# In-memory role-id cache: { guild_id: { "Tank": role_id, ... } }
_ROLE_CACHE: dict[int, dict[str, int]] = {}

# =========================
# Bot Setup
# =========================

intents = discord.Intents.default()
# Required for buttons & slash commands; message_content is only needed if you read message text
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# =========================
# Utilities
# =========================

def generate_listed_as(dungeon: str) -> str:
    """Return the title prefix for the embed."""
    return f"KC: {dungeon}"

def generate_passphrase(length: int = 8) -> str:
    """Create a random passphrase for a group."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choices(alphabet, k=length))

def _find_role_id_by_title(guild: discord.Guild, title: str) -> Optional[int]:
    """
    Return the Discord role id for a role with the given display title (case-insensitive).
    Uses an in-memory cache to avoid repeated scans of guild.roles.
    """
    cached = _ROLE_CACHE.get(guild.id, {}).get(title)
    if cached is not None:
        return cached

    role = find(lambda r: r.name.lower() == title.lower(), guild.roles)
    if role:
        _ROLE_CACHE.setdefault(guild.id, {})[title] = role.id
        return role.id
    return None

def get_role_ping(guild: discord.Guild, title: str) -> str:
    """Return a mention string for the display title, or a readable fallback like @Tank."""
    rid = _find_role_id_by_title(guild, title)
    return f"<@&{rid}>" if rid else f"@{title}"


# =========================
# Event Hooks
# =========================

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    # Global sync (use guild-scoped sync if you need faster propagation during dev)
    try:
        synced = await bot.tree.sync()
        print(f"🔁 Synced {len(synced)} slash commands.")
        for cmd in synced:
            print(f"   ↪️ /{cmd.name}")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

# Optional: keep the role cache fresh if roles are renamed/deleted
@bot.event
async def on_guild_role_update(before: discord.Role, after: discord.Role):
    _ROLE_CACHE.get(after.guild.id, {}).pop(before.name, None)
    _ROLE_CACHE.get(after.guild.id, {}).pop(after.name, None)

@bot.event
async def on_guild_role_delete(role: discord.Role):
    cache = _ROLE_CACHE.get(role.guild.id)
    if not cache:
        return
    for k, v in list(cache.items()):
        if v == role.id:
            cache.pop(k, None)


# =========================
# UI: Role Select (Creation)
# =========================

class RoleMultiSelect(discord.ui.Select):
    """
    Ephemeral dropdown shown to the creator to select required roles for this listing.
    Produces the public embed + interactive buttons.
    """
    def __init__(self, interaction: discord.Interaction, dungeon: str, key_level: int,
                 timing: Literal["Timed", "Completion"], requirements: Optional[str],
                 passphrase: Optional[str], listed_as: Optional[str], your_role: Literal["Tank","Healer","Melee DPS","Ranged DPS"]):
        all_options = [
            discord.SelectOption(label="Tank", emoji="🛡️"),
            discord.SelectOption(label="Healer", emoji="❤️‍🩹"),
            discord.SelectOption(label="Melee DPS", emoji="⚔️"),
            discord.SelectOption(label="Ranged DPS", emoji="🏹"),
        ]
        # If you want to filter out creator's current role from the required list, uncomment below:
        # options = [opt for opt in all_options if opt.label != your_role]
        options = [opt for opt in all_options]

        super().__init__(
            placeholder="Select required roles",
            min_values=1,
            max_values=len(options),
            options=options,
        )

        # We carry a small context that seeds the embed + view
        self.interaction = interaction
        self.context = {
            "dungeon": dungeon,
            "key_level": key_level,
            "timing": timing,
            "your_role": your_role,
            "requirements": requirements,
            "passphrase": passphrase or generate_passphrase(),
            "listed_as": listed_as or generate_listed_as(dungeon),
        }

    async def callback(self, interaction: discord.Interaction):
        selected_roles = self.values
        ctx = self.context

        pings = ", ".join(get_role_ping(interaction.guild, r) for r in selected_roles)

        embed = discord.Embed(
            title=f"KC: {ctx['dungeon']} +{ctx['key_level']}",
            description=(
                f"🪪 **Listed As**: `{ctx['listed_as']}`\n"
                f"🔑 **Passphrase**: ||{ctx['passphrase']}||\n"
                f"⏱️ **Timing Expectation**: {ctx['timing']}\n"
                f"👥 **Looking For**: {pings if pings else 'None'}\n"
                f"📌 **Specific Requirements**: {ctx['requirements'] or 'None'}\n"
            ),
            color=discord.Color.dark_blue(),
        )
        embed.set_footer(text="Click a role to join. Group expires in 30 minutes.")

        # Acknowledge ephemeral interaction
        await interaction.response.defer()

        # Create public view + message
        view = LFGButtonView(
            creator=interaction.user,
            creator_role=ctx["your_role"],
            required_roles=selected_roles,
            context=ctx,
        )
        view.setup_buttons()  # rows, callbacks, initial enable/disable
        public_message = await interaction.channel.send(embed=embed, view=view)
        view.message = public_message

        # Remove the ephemeral select
        await interaction.delete_original_response()
        await view.update_embed()


class RoleMultiSelectView(discord.ui.View):
    """Thin container view for RoleMultiSelect (ephemeral)."""
    def __init__(self, interaction: discord.Interaction, *args, your_role: str):
        super().__init__(timeout=180)
        self.add_item(RoleMultiSelect(interaction, *args, your_role=your_role))


# =========================
# UI: Update Required Roles (Ephemeral)
# =========================

class UpdateRequiredRoles(discord.ui.Select):
    """
    Ephemeral dropdown used to update required roles without recreating the embed.
    Updates the running LFGButtonView and refreshes the message.
    """
    def __init__(self, lfg_view: "LFGButtonView"):
        self.lfg_view = lfg_view

        options = [
            discord.SelectOption(label="Tank", emoji="🛡️"),
            discord.SelectOption(label="Healer", emoji="❤️‍🩹"),
            discord.SelectOption(label="Melee DPS", emoji="⚔️"),
            discord.SelectOption(label="Ranged DPS", emoji="🏹"),
        ]
        super().__init__(
            placeholder="Select updated required roles",
            min_values=1,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        # Normalize to internal keys
        self.lfg_view.required_roles = [role.lower().replace(" ", "") for role in self.values]
        await self.lfg_view.update_embed()

        # Replace the ephemeral view with a simple confirmation (and close it)
        await interaction.response.edit_message(content="✅ Required roles updated.", view=None)
        self.view.stop()


class UpdateRequiredRolesView(discord.ui.View):
    """Thin container view for UpdateRequiredRoles (ephemeral)."""
    def __init__(self, lfg_view: "LFGButtonView"):
        super().__init__(timeout=180)
        self.add_item(UpdateRequiredRoles(lfg_view))


# =========================
# UI: Modal — Edit Requirements Text
# =========================

class RequirementsEdit(discord.ui.Modal, title="Edit Group Requirements"):
    """
    Modal to update the 'Specific Requirements' line in the embed description.
    Only the creator can open this modal.
    """
    def __init__(self, view: "LFGButtonView"):
        super().__init__()
        self.view = view

        self.requirements = discord.ui.TextInput(
            label="New Requirements",
            placeholder="Enter updated requirements (e.g., interrupt, lust, etc.)",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200,
        )
        self.add_item(self.requirements)

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.view.message.embeds[0]
        lines = embed.description.splitlines()

        # Replace "Specific Requirements" line
        for i, line in enumerate(lines):
            if "**Specific Requirements**" in line:
                lines[i] = f"📌 **Specific Requirements**: {self.requirements.value}"
                break
        embed.description = "\n".join(lines)

        await self.view.message.edit(embed=embed, view=self.view)
        await interaction.response.send_message("✅ Requirements updated!", ephemeral=True)


# =========================
# Slash Command: /lfg
# =========================

@bot.tree.command(name="lfg", description="Create a Mythic+ group")
@app_commands.describe(
    dungeon="Dungeon name (e.g., Dawnbreaker, Priory)",
    key_level="Keystone level (e.g., 15)",
    passphrase="Choose a passphrase, or leave empty for auto-generated",
    timing="Your timing expectation",
    your_role="Which role are you playing?",
    listed_as="Optional name this group will be listed as",
    requirements="Any utilities/requirements teammates should have",
)
async def lfg(
    interaction: discord.Interaction,
    dungeon: Literal[
        "Dawnbreaker",
        "Ara-Kara",
        "Operation: Floodgate",
        "Priory of Sacred Flame",
        "Eco-Dome Al'dani",
        "Halls of Atonement",
        "Tazavesh: Streets of Wonder",
        "Tazavesh: So'leah's Gambit",
    ],
    key_level: int,
    timing: Literal["Timed", "Completion"],
    your_role: Literal["Tank", "Healer", "Melee DPS", "Ranged DPS"],
    requirements: Optional[str] = None,
    passphrase: Optional[str] = None,
    listed_as: Optional[str] = None,
):
    """
    Starts an ephemeral flow where the creator chooses required roles,
    then posts a public, interactive LFG listing with role buttons.
    """
    await interaction.response.send_message(
        "Please select the roles you're looking for:",
        view=RoleMultiSelectView(
            interaction,
            dungeon,
            key_level,
            timing,
            requirements,
            passphrase,
            listed_as,
            your_role=your_role,
        ),
        ephemeral=True,
    )


# =========================
# View: LFGButtonView
# =========================

class LFGButtonView(discord.ui.View):
    """
    Main interactive view attached to the public LFG message.
    Handles:
      - role buttons (Tank/Healer/Melee/Ranged) with dynamic enabled/disabled states
      - edit requirements (modal)
      - leave party
      - close group
      - auto-prompt creator to update required roles after they switch roles
    """
    def __init__(self, creator: discord.User, creator_role: str, required_roles: list[str], context: dict):
        super().__init__(timeout=1800)
        self.creator = creator
        self.creator_role = creator_role
        self.creator_original_role = creator_role.lower().replace(" ", "")
        self.context = context
        self.closed = False
        self.required_roles = [r.lower().replace(" ", "") for r in required_roles]
        self.members: dict[str, list[str]] = {
            "tank": [],
            "healer": [],
            "meleedps": [],
            "rangeddps": [],
        }

        # Message reference is set after send
        self.message: Optional[discord.Message] = None

        # Create all buttons up-front (manual approach = full layout control)
        self.tank = discord.ui.Button(label="🛡️ Tank", style=discord.ButtonStyle.primary, custom_id="tank")
        self.healer = discord.ui.Button(label="❤️‍🩹 Healer", style=discord.ButtonStyle.primary, custom_id="healer")
        self.meleedps = discord.ui.Button(label="⚔️ Melee DPS", style=discord.ButtonStyle.primary, custom_id="meleedps")
        self.rangeddps = discord.ui.Button(label="🏹 Ranged DPS", style=discord.ButtonStyle.primary, custom_id="rangeddps")

        self.edit_requirements = discord.ui.Button(label="✏️ Edit Requirements", style=discord.ButtonStyle.secondary)
        self.leave = discord.ui.Button(label="🚪 Leave Party", style=discord.ButtonStyle.secondary)
        self.cancel = discord.ui.Button(label="❌ Close Group", style=discord.ButtonStyle.secondary)

        # Auto-assign creator to their chosen role at creation time
        role_key = self.creator_original_role  # already normalized
        self.members[role_key].append(creator.mention)

    # ---- internal: layout/state helpers ----

    def _apply_role_button_states(self):
        """Enable only required roles (and disable all if the group is closed)."""
        for btn in (self.tank, self.healer, self.meleedps, self.rangeddps):
            btn.disabled = (btn.custom_id not in self.required_roles) or self.closed

    def setup_buttons(self):
        """Bind callbacks, set rows, apply states, then add to the view."""
        # Bind callbacks
        self.tank.callback = self._handle_tank
        self.healer.callback = self._handle_healer
        self.meleedps.callback = self._handle_melee
        self.rangeddps.callback = self._handle_ranged
        self.edit_requirements.callback = self._handle_edit_requirements
        self.leave.callback = self._handle_leave
        self.cancel.callback = self._handle_cancel

        # Row layout → Row 0: roles, Row 1: edit, Row 2: controls
        self.tank.row = self.healer.row = self.meleedps.row = self.rangeddps.row = 0
        self.edit_requirements.row = 1
        self.leave.row = self.cancel.row = 2

        # Apply initial disabled/enabled flags
        self._apply_role_button_states()

        # Add to view in visual order
        for btn in (
            self.tank, self.healer, self.meleedps, self.rangeddps,
            self.edit_requirements, self.leave, self.cancel
        ):
            self.add_item(btn)

    # ---- button callbacks ----

    async def _handle_tank(self, interaction: discord.Interaction):
        await self._join_role(interaction, "tank")

    async def _handle_healer(self, interaction: discord.Interaction):
        await self._join_role(interaction, "healer")

    async def _handle_melee(self, interaction: discord.Interaction):
        await self._join_role(interaction, "meleedps")

    async def _handle_ranged(self, interaction: discord.Interaction):
        await self._join_role(interaction, "rangeddps")

    async def _handle_edit_requirements(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator.id:
            await interaction.response.send_message("🚫 Only the group creator can edit the requirements.", ephemeral=True)
            return
        await interaction.response.send_modal(RequirementsEdit(self))

    async def _handle_leave(self, interaction: discord.Interaction):
        if interaction.user.id == self.creator.id:
            await interaction.response.send_message("🚫 You can't leave the party as the creator. Use **Close Group** instead.", ephemeral=True)
            return

        user_mention = interaction.user.mention
        left = False
        for role, users in self.members.items():
            if user_mention in users:
                users.remove(user_mention)
                left = True

        if left:
            await interaction.response.send_message("👋 You've left the party.", ephemeral=True)
            await self.update_embed()
        else:
            await interaction.response.send_message("⚠️ You're not in the party.", ephemeral=True)

    async def _handle_cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator.id:
            await interaction.response.send_message("🚫 Only the creator can close the group.", ephemeral=True)
            return

        # Strike through description (preserving spoilers)
        embed = self.message.embeds[0]
        lines = embed.description.split("\n")
        struck = []
        for line in lines:
            if "🔑" in line and "||" in line:
                parts = line.split("||")
                if len(parts) == 3:
                    struck.append(f"🔑 **Passphrase**: ||~~{parts[1]}~~||")
                else:
                    struck.append(f"~~{line}~~")
            else:
                struck.append(f"~~{line}~~")
        embed.description = "\n".join(struck)
        embed.set_footer(text="❌ This group has been closed.")

        self.closed = True
        for item in self.children:
            item.disabled = True

        await self.message.edit(embed=embed, view=self)
        await interaction.response.send_message("✅ Group has been closed.", ephemeral=True)

    # ---- core behavior ----

    async def update_embed(self):
        """Rebuild the fields and reapply button states, then edit the message."""
        embed = self.message.embeds[0]
        embed.clear_fields()

        role_labels = {
            "tank": "🛡️ Tank",
            "healer": "❤️‍🩹 Healer",
            "meleedps": "⚔️ Melee DPS",
            "rangeddps": "🏹 Ranged DPS",
        }

        # Fields for each role
        for role, users in self.members.items():
            role_label = role_labels[role]
            user_list = [
                f"{i+1}. {user} 👑" if user == self.creator.mention else f"{i+1}. {user}"
                for i, user in enumerate(users)
            ]

            if role in self.required_roles:
                value = "\n".join(user_list) or "*— empty —*"
            else:
                value = "\n".join(user_list) if users else "*Filled Spot*"

            embed.add_field(name=f"{role_label} ({len(users)})", value=value, inline=False)

        # Refresh the “Looking For” line with updated pings
        lines = embed.description.splitlines()
        for i, line in enumerate(lines):
            if "Looking For" in line:
                pings = ", ".join(
                    get_role_ping(self.message.guild, ROLE_KEY_TO_TITLE[k])
                    for k in self.required_roles
                )
                lines[i] = f"👥 **Looking For**: {pings if pings else 'None'}"
                break
        embed.description = "\n".join(lines)

        # Reapply button states (required roles, closed state)
        self._apply_role_button_states()

        await self.message.edit(embed=embed, view=self)

    async def _join_role(self, interaction: discord.Interaction, role: str):
        """
        Assign the interacting user to the chosen role button.
        If the creator changes roles, prompt them to update required roles (ephemeral).
        """
        user_mention = interaction.user.mention

        # Remove from any previous role first (single-role membership)
        for r in self.members:
            if user_mention in self.members[r]:
                self.members[r].remove(user_mention)

        # Add to the selected new role
        self.members[role].append(user_mention)

        # Prompt creator to confirm/update required roles every time they switch
        if interaction.user.id == self.creator.id:
            await interaction.response.send_message(
                "👑 You changed your role. Please confirm or update the required roles:",
                view=UpdateRequiredRolesView(self),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"✅ You joined as **{role.replace('dps', ' DPS').capitalize()}**!",
                ephemeral=True,
            )

        if self.message:
            await self.update_embed()

    async def on_timeout(self):
        """
        After 30 minutes, auto-expire the post:
        - strike title/description
        - disable all buttons
        """
        if self.closed or not self.message:
            return

        embed = self.message.embeds[0]
        embed.title = f"~~{embed.title}~~"
        # Carefully strike description lines to avoid breaking spoilers, if desired.
        embed.description = f"~~{embed.description}~~"
        embed.set_footer(text="⏳ Group expired after 30 minutes.")

        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass


# =========================
# Entrypoint
# =========================

if __name__ == "__main__":
    bot.run(TOKEN)
