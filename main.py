import os
import io
import math
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

# --- config ---
MAX_HEARTS = 20  # max hearts to render before showing "..." and the numeric total

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
    """
    Return HP for user in guild. If not present, initialize at 6 and return 6.
    """
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


def remove_player(uid: int, guild_id: int):
    """Remove player row from DB."""
    c.execute("DELETE FROM Players WHERE uid = ? AND guild_id = ?", (uid, guild_id))
    conn.commit()


def set_hp(uid: int, guild_id: int, hp: int) -> bool:
    """
    Set hp for a player.
    If hp <= 0: remove the player from the database and return True to indicate deletion.
    Otherwise upsert the player's hp and return False.
    """
    if hp <= 0:
        remove_player(uid, guild_id)
        return True

    c.execute(
        "INSERT INTO Players(uid, guild_id, hp) VALUES(?, ?, ?) "
        "ON CONFLICT(uid, guild_id) DO UPDATE SET hp = ?",
        (uid, guild_id, hp, hp),
    )
    conn.commit()
    return False


def render_hearts(hp: int, max_hearts: int = MAX_HEARTS) -> str:
    """
    Return a hearts string capped at `max_hearts`. If hp > max_hearts,
    append ' ...' and the numeric total will be shown by the caller.
    Example outputs:
      - hp=6 -> '❤️❤️❤️❤️❤️❤️'
      - hp=40 -> '❤️❤️...'
    """
    if hp <= 0:
        return ""
    if hp <= max_hearts:
        return "❤️" * hp
    return "❤️" * max_hearts + " ..."


def hearts_display(uid: int, guild: discord.Guild) -> str | None:
    """
    Return a string showing hearts for a specific user in a guild.
    This uses get_hp so a missing user is auto-initialized to 6 HP.
    Returns None if HP <= 0 (meaning not in list).
    Example: "Alice: ❤️❤️❤️ ... (40)"
    """
    hp = get_hp(uid, guild.id)
    if hp <= 0:
        return None
    hearts = render_hearts(hp)
    member = guild.get_member(uid)
    display_name = member.display_name if member else f"<@{uid}>"
    return f"{display_name}: {hearts} ({hp})"


def has_role(role_name: str):
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False

        # Get the Member object for the user in this guild
        member: discord.Member | None = interaction.guild.get_member(
            interaction.user.id
        )
        if member is None:
            return False

        # Check if they have the role
        role = discord.utils.get(member.roles, name=role_name)
        return role is not None

    return app_commands.check(predicate)


# --- events ---
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready as {bot.user}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message(
            "You do not have permission to use this command.", ephemeral=True
        )


# --- slash commands ---
@bot.tree.command(
    name="hp_show", description="Check HP of a specific member (mods only)"
)
@app_commands.describe(member="The member to check")
@has_role("slime")
async def hp_show(interaction: discord.Interaction, member: discord.Member):
    """Show HP hearts for a specific member (auto-initializes to 6 if not present)."""
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    display = hearts_display(member.id, guild)
    if display is None:
        await interaction.response.send_message(
            f"{member.display_name} is not on the HP list.", ephemeral=True
        )
    else:
        await interaction.response.send_message(display)


@bot.tree.command(name="hp_add", description="Add HP to a member (mods only)")
@app_commands.describe(
    member="Select the member to modify", amount="Amount of HP to add"
)
@has_role("slime")
async def hp_add(
    interaction: discord.Interaction, member: discord.Member, amount: int = 1
):
    """Add HP to a member. Only moderators with the slime role."""
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    current = get_hp(member.id, guild.id)
    new_hp = current + amount
    _deleted = set_hp(member.id, guild.id, new_hp)

    # show capped hearts plus numeric total
    hearts = render_hearts(new_hp)
    await interaction.response.send_message(
        f"Added {amount} HP to {member.display_name}. Now at {hearts} ({new_hp})."
    )


@bot.tree.command(name="hp_remove", description="Remove HP from a member (mods only)")
@app_commands.describe(
    member="Select the member to modify", amount="Amount of HP to remove"
)
@has_role("slime")
async def hp_remove(
    interaction: discord.Interaction, member: discord.Member, amount: int = 1
):
    """Remove HP from a member. Only moderators with the slime role."""
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    current = get_hp(member.id, guild.id)
    new_hp = max(current - amount, 0)
    deleted = set_hp(member.id, guild.id, new_hp)

    if deleted:
        # Player reached 0 and was removed from DB
        await interaction.response.send_message(
            f"Removed {amount} HP from {member.display_name}. Now at 0 HP — removed from player list."
        )
    else:
        hearts = render_hearts(new_hp)
        await interaction.response.send_message(
            f"Removed {amount} HP from {member.display_name}. Now at {hearts} ({new_hp})."
        )


@bot.tree.command(
    name="players", description="Show all players and their HP (mods only)"
)
@has_role("slime")
async def players(interaction: discord.Interaction):
    """List all players in the current server and their HP visually with ❤️.
    Also remove DB entries for users no longer in the server or with 0 HP.
    Handles long output by paginating or uploading a file.
    """
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    # Fetch rows for this guild
    c.execute("SELECT uid, hp FROM Players WHERE guild_id = ?", (guild.id,))
    rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("No players found.")
        return

    lines = []
    removed_any = False
    for uid, hp in rows:
        member = guild.get_member(uid)
        if member is None:
            # member left server -> remove from DB
            remove_player(uid, guild.id)
            removed_any = True
            continue

        # sanity: if hp <= 0 remove (defensive)
        if hp <= 0:
            remove_player(uid, guild.id)
            removed_any = True
            continue

        # use capped hearts display to avoid message bloat
        hearts = render_hearts(hp)
        display_name = member.display_name
        lines.append(f"{display_name}: {hearts} ({hp})")

    if not lines:
        msg = "No players found."
        if removed_any:
            msg += " (Removed entries for members who left or had 0 HP.)"
        await interaction.response.send_message(msg)
        return

    header = "**Players HP:**\n"
    if removed_any:
        footer = "\n\n(Also removed entries for members who left or had 0 HP.)"
    else:
        footer = ""

    full_text = header + "\n".join(lines) + footer

    # Safety thresholds
    SINGLE_MSG_LIMIT = 1900  # safe under Discord's 2000-char limit
    MAX_PAGES = 5  # if <= 5 pages, paginate; otherwise send file
    page_size = SINGLE_MSG_LIMIT

    if len(full_text) <= SINGLE_MSG_LIMIT:
        # short — single message
        await interaction.response.send_message(full_text)
        return

    # Determine number of pages if we split by characters
    num_pages = math.ceil(len(full_text) / page_size)

    if num_pages <= MAX_PAGES:
        # Paginate: send first as response, rest as followups
        chunks = [
            full_text[i : i + page_size] for i in range(0, len(full_text), page_size)
        ]
        # Send first chunk as initial response
        await interaction.response.send_message(chunks[0])
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)
        return

    # Too large — send as a file attachment
    fp = io.BytesIO(full_text.encode("utf-8"))
    fp.seek(0)
    await interaction.response.send_message(
        "Output too long — uploading as `players.txt`.",
        file=discord.File(fp, filename="players.txt"),
    )


bot.run(TOKEN)
