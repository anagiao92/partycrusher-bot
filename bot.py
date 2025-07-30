import discord
from discord.ext import commands
import os
import random
import string
from dotenv import load_dotenv
from typing import Literal

#Global Variables
# Load environment
load_dotenv(dotenv_path=".env.dev")
TOKEN = os.getenv("DISCORD_TOKEN")
MY_GUILD = discord.Object(id=813092953236176928)
# Role mention mappings (replace with your actual role IDs)
ROLE_PINGS = {
    "Tank": "<@&1400104959491444786>",
    "Healer": "<@&1400105203616976946>",
    "Melee DPS": "<@&1400105285678272697>",
    "Ranged DPS": "<@&1400105294456946811>",
    #"Support": "<@&1400105300865978418>",
}

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    #async def cleanupguild():
     #  test_guild = discord.Object(id=813092953236176928)  # Replace with your actual server ID

     #   try:
     #       bot.tree.clear_commands(guild=test_guild)  # ✅ no await here
     #       await bot.tree.sync(guild=test_guild)
     #       print("🧹 Cleared and resynced test guild commands.")
     #   except Exception as e:
     #       print(f"❌ Failed to clear commands: {e}")

    #await cleanupguild()

    #async def cleanupglobal():  

     #   try:
     #      bot.tree.clear_commands(guild=None)  # ✅ no await here
     #       await bot.tree.sync()
     #       print("🧹 Cleared and resynced global commands.")
     #   except Exception as e:
     #       print(f"❌ Failed to clear commands: {e}")

     # await cleanupglobal()

    try:
        synced = await bot.tree.sync()
        # Force clear old guild commands
        #bot.tree.clear_commands(guild=MY_GUILD)
        #synced = await bot.tree.sync(guild=MY_GUILD)
        print(f"🔁 Synced {len(synced)} slash commands.")
        for cmd in synced:
            print(f"   ↪️ /{cmd.name}")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")


# Utility: random group name and passphrase
def generate_listed_as(dungeon):
    return f"KC: {dungeon}"

def generate_passphrase():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

class RoleMultiSelect(discord.ui.Select):
    def __init__(self, interaction, dungeon, key_level, timing, requirements, passphrase, listed_as, your_role):
        all_options = [
            discord.SelectOption(label="Tank", emoji="🛡️"),
            discord.SelectOption(label="Healer", emoji="❤️‍🩹"),
            discord.SelectOption(label="Melee DPS", emoji="⚔️"),
            discord.SelectOption(label="Ranged DPS", emoji="🏹"),
            #discord.SelectOption(label="Support", emoji="🤝"),
        ]

        # Filter out creator's role
        options = [opt for opt in all_options] #if opt.label != your_role]

        super().__init__(
            placeholder="Select required roles",
            min_values=1,
            max_values=len(options),
            options=options
        )

        self.interaction = interaction
        self.context = {
            "dungeon": dungeon,
            "key_level": key_level,
            "timing": timing,
            "your_role" :your_role,
            "requirements": requirements,
            "passphrase": passphrase or generate_passphrase(),
            "listed_as": listed_as or generate_listed_as(dungeon)
        }


    async def callback(self, interaction: discord.Interaction):
        selected_roles = self.values
        ctx = self.context

        embed = discord.Embed(
            title=f"KC: {ctx['dungeon']} +{ctx['key_level']}",
            description=(
                f"🪪 **Listed As**: `{ctx['listed_as']}`\n"
                f"🔑 **Passphrase**: ||{ctx['passphrase']}||\n"
                f"⏱️ **Timing Expectation**: {ctx['timing']}\n"
                f"👥 **Looking For**: {', '.join(ROLE_PINGS[r] for r in selected_roles)}\n"
                f"📌 **Specific Requirements**: {ctx['requirements']}\n"
            ),
            color=discord.Color.dark_blue()
        )
        embed.set_footer(text="Click a role to join. Group expires in 30 minutes.")

        # ✅ Acknowledge the ephemeral interaction silently
        await interaction.response.defer()

        # ✅ Send the embed publicly in the channel
        view = LFGButtonView(creator=interaction.user, creator_role=ctx["your_role"], required_roles=[r.lower().replace(" ", "") for r in selected_roles])
        public_message = await interaction.channel.send(embed=embed, view=view)

        # ✅ Save reference to the message in the view
        view.message = public_message

        # ✅ Delete the original ephemeral message (optional)
        await interaction.delete_original_response()
        await view.update_embed()
        

class RoleMultiSelectView(discord.ui.View):
    def __init__(self, interaction, *args, your_role):
        super().__init__(timeout=180)
        self.add_item(RoleMultiSelect(interaction, *args, your_role=your_role))

class RequirementsEdit(discord.ui.Modal, title="Edit Group Requirements"):
    def __init__(self, view: 'LFGButtonView'):
        super().__init__()
        self.view = view

        self.requirements = discord.ui.TextInput(
            label="New Requirements",
            placeholder="Enter updated requirements (e.g. interrupt, lust, etc.)",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=200,
        )
        self.add_item(self.requirements)

    async def on_submit(self, interaction: discord.Interaction):
        embed = self.view.message.embeds[0]

        # Find and update requirements line
        lines = embed.description.splitlines()
        for i, line in enumerate(lines):
            if "**Specific Requirements**" in line:
                lines[i] = f"📌 **Specific Requirements**: {self.requirements.value}"
                break
        embed.description = "\n".join(lines)

        await self.view.message.edit(embed=embed, view=self.view)
        await interaction.response.send_message("✅ Requirements updated!", ephemeral=True)

# LFG command
#@bot.tree.command(name="lfgt", description="Create a Mythic+ group (test)", guild=MY_GUILD)
@bot.tree.command(name="lfg", description="Create a Mythic+ group")

@discord.app_commands.describe(
    dungeon="Dungeon name (e.g., Dawnbreaker, Priory)",
    key_level="Keystone level (e.g., 15)",
    passphrase = "Choose a passphrase for your group or leave empty for an autogenerated one",
    timing = "Your timing expectation",
    your_role="Which role are you playing?",
    listed_as="Optional name this group will be listed as",
    requirements="Any utility or requirements you want your party members to have"
)

async def lfg(
    interaction: discord.Interaction,
    dungeon: Literal["Dawnbreaker","Ara-Kara","Operation: Floodgate","Priory of Sacred Flame","Eco-Dome Al'dani","Halls of Atonement","Tazavesh: Streets of Wonder","Tazavesh: So'leah's Gambit"],
    key_level: int,
    timing: Literal["Timed","Completion"],
    your_role: Literal["Tank","Healer","Melee DPS","Ranged DPS"],
    #your_role: Literal["Tank","Healer","Melee DPS","Ranged DPS","Support"],
    requirements: str = None, #should be mandatory??
    passphrase: str = None, 
    listed_as: str = None
    ):

    await interaction.response.send_message(
        "Please select the roles you're looking for:",
        view=RoleMultiSelectView(interaction, 
                                 dungeon, key_level, timing, requirements, passphrase, listed_as, 
                                 your_role=your_role)
        ,ephemeral=True
    )    

# Role Button View Class #
class LFGButtonView(discord.ui.View):
    ## Initiate parameters and variables ##
    def __init__(self, creator: discord.User, creator_role: str, required_roles: list[str]):
        #Variables
        super().__init__(timeout=1800)
        self.creator = creator
        self.creator_role = creator_role
        self.closed = False
        self.required_roles = [r.lower().replace(" ", "") for r in required_roles]
        self.members = {
            "tank": [],
            "healer": [],
            "meleedps": [],
            "rangeddps": []
            #,"support": []
        }

        self.message = None

        # Auto-assign creator to their role
        role_key = creator_role.lower().replace(" ", "")  # E.g., "Melee DPS" → "meleedps"
        self.members[role_key].append(creator.mention)
    ##    
    ## Update the Embed deffinition ##
    async def update_embed(self):
        embed = self.message.embeds[0]
        embed.clear_fields()

        role_labels = {
            "tank": "🛡️ Tank",
            "healer": "❤️‍🩹 Healer",
            "meleedps": "⚔️ Melee DPS",
            "rangeddps": "🏹 Ranged DPS"
            #,"support": "🤝 Support"
        }

        for role, users in self.members.items():
            
            if role not in self.required_roles:
                value = "*Filled Spot*"  # Role is not needed
            else:
                value = "\n".join(
                    f"{i+1}. {user} 👑" if user == self.creator.mention else f"{i+1}. {user}"
                    for i, user in enumerate(users)
                ) or "*— empty —*"

            embed.add_field(name=f"{role_labels[role]} ({len(users)})", value=value, inline=False)

        await self.message.edit(embed=embed, view=self)
    ##    
    ## Join Roles deffinition ##
    async def _join_role(self, interaction: discord.Interaction, role: str):
        user_mention = interaction.user.mention

        for r in self.members:
            if user_mention in self.members[r]:
                self.members[r].remove(user_mention)

        self.members[role].append(user_mention)

        await interaction.response.send_message(
            f"✅ You joined as **{role.replace('dps',' DPS').capitalize()}**!", ephemeral=True
        )

        if self.message:
            await self.update_embed()
    ##
    ## Timeout deffinition ##
    async def on_timeout(self):
        if self.closed or not self.message:
            return
        
        #Strikethrough the embed text and set footer
        embed = self.message.embeds[0]
        embed.title = f"~~{embed.title}~~"
        embed.description = f"~~{embed.description}~~"
        embed.set_footer(text="⏳ Group expired after 30 minutes.")

        for item in self.children:
            item.disabled = True
        
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass 
    ##   
    #Button Definition 
    #Tank
    @discord.ui.button(label="🛡️ Tank", style=discord.ButtonStyle.primary)
    async def tank(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._join_role(interaction, "tank")
    #Healer
    @discord.ui.button(label="❤️‍🩹 Healer", style=discord.ButtonStyle.primary)
    async def healer(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._join_role(interaction, "healer")
    #Melee DPS
    @discord.ui.button(label="⚔️ Melee DPS", style=discord.ButtonStyle.primary)
    async def meleedps(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._join_role(interaction, "meleedps")
    #Ranged DPS
    @discord.ui.button(label="🏹 Ranged DPS", style=discord.ButtonStyle.primary)
    async def rangeddps(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._join_role(interaction, "rangeddps")
    #Support
    #@discord.ui.button(label="🤝 Support", style=discord.ButtonStyle.primary)
    #async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
    #    await self._join_role(interaction, "support")
    #Leave
    @discord.ui.button(label="✏️ Edit Requirements", style=discord.ButtonStyle.secondary)
    async def edit_requirements(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator.id:
            await interaction.response.send_message("🚫 Only the group creator can edit the requirements.", ephemeral=True)
            return

        await interaction.response.send_modal(RequirementsEdit(self))

    @discord.ui.button(label="🚪 Leave Party", style=discord.ButtonStyle.secondary)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.creator.id:
            await interaction.response.send_message("🚫 You can't leave the party as a creator. Use **Close Group** instead.", ephemeral=True)
            return
        user_mention = interaction.user.mention #Interacting User @mention
        left = False                            #left or not boolean

        for role, users in self.members.items():
                if user_mention in users:
                    users.remove(user_mention)
                    left = True
        
        if left:
            await interaction.response.send_message("👋  You've left the party", ephemeral=True)
            await self.update_embed()
        else:
            await interaction.response.send_message("⚠️ You're not in the party", ephemeral=True)
    #Cancel
    @discord.ui.button(label="❌ Close Group", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator.id:
            await interaction.response.send_message("🚫 You can't cancel the party if you're not the creator. Use **Leave Party** instead.", ephemeral=True)
            return
        
        #Strikethrough the embed text and set footer
        embed = self.message.embeds[0]
        lines = embed.description.split("\n")
        struck_lines = []

        for line in lines:
            if "🔑" in line:  # Preserve spoiler formatting
                parts = line.split("||")
                if len(parts) == 3:
                    struck = f"🔑 **Passphrase**: ||~~{parts[1]}~~||"
                else:
                    struck = f"~~{line}~~"
            else:
                struck = f"~~{line}~~"
            struck_lines.append(struck)

        embed.description = "\n".join(struck_lines)
        embed.set_footer(text="❌ This group has been closed.")

        self.closed = True #Flag if it was closed
        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await self.message.edit(embed=embed, view=self)
        await interaction.response.send_message("✅ Group has been closed.", ephemeral=True)

# Run bot
bot.run(TOKEN)