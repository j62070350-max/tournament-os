# Mech Arena Knowledge Base

This directory powers the Mech Arena AI Assistant's knowledge retrieval system.

## How it works

All `.md` files in this directory (and any subdirectory) are automatically loaded
at bot startup and indexed for fast BM25 search. The bot retrieves relevant chunks
before every AI response, grounding answers in real data instead of model memory.

## Structure

```
knowledge/
├── mechs/          Mech stats, abilities, tier lists, strengths/weaknesses
├── weapons/        Weapon stats, DPS, range, reload, combinations
├── pilots/         Pilot abilities and mech pairings
├── implants/       Implant effects and recommended builds
├── maps/           Map layouts, choke points, positioning
├── patches/        Patch notes and meta changes
├── strategies/     General strategies and team compositions
└── progression/    Beginner to advanced guides
```

## Adding knowledge

1. Create a `.md` file in the appropriate folder
2. Start with a `# Title` heading
3. Write clear, factual content with accurate stats
4. Run `/reload-mech-knowledge` in Discord — no restart needed

## File format tips

- Use `# Title` for the document title (used in search results)
- Use `##` and `###` for sections
- Bullet lists work great for stats
- Keep files focused (one mech, one weapon, one map per file)
- Thousands of files are supported

## Live reload

Run `/reload-mech-knowledge` in any Discord server where the bot is active to
reload all knowledge files from disk without restarting the bot.
