# slime-bot

A Discord bot that tracks health points (HP) for server members. Each member starts with 6 HP, and moderators can adjust HP as needed.

## Features

* `/hp` - Shows your current HP with hearts
* `/hp_add` - Adds HP to a member (mods only)
* `/hp_remove` - Removes HP from a member (mods only)
* `/players` - Lists all players in the server with their HP visually using hearts

## Data Storage

* Uses SQLite to store HP for each member per server
* Data persists as long as the bot is running and the database file is preserved

## Requirements

* Python 3.10 or higher
* Packages: `discord.py`, `python-dotenv`
* `.env` file with your Discord bot token

Example `.env` file:

```
DISCORD_TOKEN=your_bot_token_here
```

## Running the Bot

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the bot:

```bash
python main.py
```