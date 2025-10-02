# slime-bot

A Discord bot that tracks health points (HP) for server members.  
Each member starts with **6 HP**, shown visually as ❤️.  

## Features

* `/hp_show @member` – Shows the HP of a specific member (auto-initializes at 6 if not present)  
* `/hp_add @member <amount>` – Adds HP to a member (**requires `slime` role**)  
* `/hp_remove @member <amount>` – Removes HP from a member (**requires `slime` role**)  
  * If a member’s HP drops to 0, they are removed from the list  
* `/players` – Lists all players in the server and their HP visually (**requires `slime` role**)  
  * Also cleans up database entries for members who left the server or have 0 HP  

## Data Storage

* Uses **SQLite** to store HP for each member per server  
* Data persists as long as the database file (`state.db`) is preserved  

## Requirements

* **Python 3.10+**  
* Packages:  
  * `discord.py`  
  * `python-dotenv`  

## Setup

1. Clone the repository
2. Create a `.env` file with your bot token:

   ```env
   DISCORD_TOKEN=your_bot_token_here
