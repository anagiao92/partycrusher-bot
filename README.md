# WoW Mythic+ Group Listing Bot 

A Discord bot for World of Warcraft Mythic+ group creation and coordination. Inspired by [Dungeon Buddy](https://github.com/KieranChambers/Dungeon-Buddy).

## Features

- Slash commands:
  - `/lfg` – Interactive group creation
  - `/lfgquick` – Quick group creation via string (coming soon)
  - `/lfghistory` – View past groups and passphrases (coming soon)
  - `/lfgstats` – Group creation stats (coming soon)

- Role selection with buttons
- Dungeon/key info tracking
- Group timeouts & auto-cleanup
- Random `listed_as` name and passphrase generation

## Getting Started

### Requirements
- Python 3.10+
- Discord bot token
- `discord.py`, `python-dotenv`

### Setup
```bash
python -m venv venv
source venv/bin/activate      # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.dev .env
python bot.py
