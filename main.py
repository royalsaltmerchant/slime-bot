import os
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise SystemExit("Missing DISCORD_TOKEN in .env file")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- database setup ---
conn = sqlite3.connect("state.db", check_same_thread=False)
c = conn.cursor()
c.execute(
    """CREATE TABLE IF NOT EXISTS Players (
        uid INTEGER,
        guild_id INTEGER,
        hp INTEGER DEFAULT 6,
        PRIMARY KEY(uid, guild_id)
    )"""
)
conn.commit()


# --- helpers ---
def get_hp(uid: int, guild_id: int) -> int:
    c.execute("SELECT hp FROM Players WHERE uid = ? AND guild_id = ?", (uid, guild_id))
    row = c.fetchone()
    if row:
        return row[0]
    # initialize with 6 HP if not found
    c.execute(
        "INSERT INTO Players(uid, guild_id, hp) VALUES(?, ?, ?)", (uid, guild_id, 6)
    )
    conn.commit()
    return 6


def set_hp(uid: int, guild_id: int, hp: int):
    c.execute(
        "INSERT INTO Players(uid, guild_id, hp) VALUES(?, ?, ?) "
        "ON CONFLICT(uid, guild_id) DO UPDATE SET hp = ?",
        (uid, guild_id, hp, hp),
    )
    conn.commit()


# --- events ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready as {bot.user}")


# --- slash commands ---
@bot.tree.command(name="hp", description="Check your current HP")
async def hp(interaction: discord.Interaction):
    """Show your current HP as hearts."""
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    current = get_hp(interaction.user.id, guild.id)
    hearts = "❤️" * current
    await interaction.response.send_message(
        f"{interaction.user.display_name} has {hearts} ({current})."
    )


@bot.tree.command(name="hp_add", description="Add HP to a member (mods only)")
@app_commands.describe(
    member="Select the member to modify", amount="Amount of HP to add"
)
@app_commands.default_permissions(administrator=True)
async def hp_add(
    interaction: discord.Interaction, member: discord.Member, amount: int = 1
):
    """Add HP to a member. Only administrators."""
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    current = get_hp(member.id, guild.id)
    set_hp(member.id, guild.id, current + amount)
    await interaction.response.send_message(
        f"Added {amount} HP to {member.display_name}. Now at {current + amount} HP."
    )


@bot.tree.command(name="hp_remove", description="Remove HP from a member (mods only)")
@app_commands.describe(
    member="Select the member to modify", amount="Amount of HP to remove"
)
@app_commands.default_permissions(administrator=True)
async def hp_remove(
    interaction: discord.Interaction, member: discord.Member, amount: int = 1
):
    """Remove HP from a member. Only administrators."""
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    current = get_hp(member.id, guild.id)
    new_hp = max(current - amount, 0)
    set_hp(member.id, guild.id, new_hp)
    await interaction.response.send_message(
        f"Removed {amount} HP from {member.display_name}. Now at {new_hp} HP."
    )


@bot.tree.command(
    name="players", description="Show all players and their HP (mods only)"
)
@app_commands.default_permissions(administrator=True)
async def players(interaction: discord.Interaction):
    """List all players in the current server and their HP visually with ❤️."""
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    c.execute("SELECT uid, hp FROM Players WHERE guild_id = ?", (guild.id,))
    rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No players found.")
        return

    lines = []
    for uid, hp in rows:
        member = guild.get_member(uid)
        hearts = "❤️" * hp
        if member:
            lines.append(f"{member.display_name}: {hearts} ({hp})")
        else:
            # member left server
            lines.append(f"<@{uid}>: {hearts} ({hp})")

    await interaction.response.send_message(f"**Players HP:**\n" + "\n".join(lines))


bot.run(TOKEN)
