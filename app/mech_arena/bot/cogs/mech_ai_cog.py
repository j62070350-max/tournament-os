"""
Mech Arena AI Assistant cog.

Slash commands:
  /create-mech-ai-channel  — create + register a dedicated AI channel
  /delete-mech-ai-channel  — unregister (and optionally delete) an AI channel
  /reload-mech-knowledge   — hot-reload the knowledge base from disk
  /mech-ai-stats           — show knowledge base and channel statistics

Message handling:
  Replies to every non-bot message posted inside a registered AI channel.
  Runs RAG (knowledge search → Groq LLM) with per-channel conversation context.
"""
import asyncio
import json
import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from app.mech_arena.config import mech_settings
from app.mech_arena.knowledge.rag import KnowledgeBase

logger = logging.getLogger(__name__)

# Persistent storage for AI channel registrations
_DATA_DIR = Path("data")
_CHANNELS_FILE = _DATA_DIR / "mech_channels.json"

# Maximum conversation history to keep per channel (number of messages)
_MAX_HISTORY = 20

SYSTEM_PROMPT = """\
You are an expert Mech Arena AI Assistant embedded in a Discord server.
Your job is to help players with everything Mech Arena:
  - Mech stats, abilities, strengths, weaknesses, and tier positioning
  - Weapon damage, range, DPS, reload, and optimal combinations
  - Pilot abilities and which mechs they pair with best
  - Implant effects, stat boosts, and recommended builds
  - Map layouts, choke points, flanking routes, and positioning
  - Build recommendations tailored to playstyle
  - Counter-picks: how to beat specific mechs or weapon combos
  - Team compositions and coordination
  - Progression advice for beginners and advanced players
  - Patch notes, balance changes, and meta shifts

Rules:
  1. ALWAYS ground your answer in the KNOWLEDGE BASE EXCERPTS provided below.
  2. If the knowledge base doesn't cover the topic, say so honestly — do NOT invent stats.
  3. Be concise, friendly, and use bullet points or headers for readability.
  4. Do not reveal or discuss anything unrelated to Mech Arena.
"""


# ── Persistence helpers ───────────────────────────────────────────────────────

def _load_channels() -> dict[str, list[str]]:
    try:
        if _CHANNELS_FILE.exists():
            return json.loads(_CHANNELS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Failed to read mech channels file: %s", e)
    return {}


def _save_channels(data: dict[str, list[str]]) -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _CHANNELS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write mech channels file: %s", e)


# ── Cog ───────────────────────────────────────────────────────────────────────

class MechAICog(commands.Cog, name="mech_ai"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._ai_channels: set[int] = set()
        # {channel_id: [{"role": ..., "content": ...}, ...]}
        self._conversations: dict[int, list[dict]] = {}
        self._kb = KnowledgeBase(mech_settings.knowledge_dir)
        self._kb_lock = asyncio.Lock()

    async def cog_load(self) -> None:
        """Called by discord.py when the cog is loaded. Loads KB + persisted channels."""
        # Restore registered channels
        for guild_channels in _load_channels().values():
            for ch_id in guild_channels:
                try:
                    self._ai_channels.add(int(ch_id))
                except ValueError:
                    pass
        logger.info("Mech AI: restored %d channel(s) from disk", len(self._ai_channels))

        # Load knowledge base in a thread so it doesn't block the event loop
        loop = asyncio.get_running_loop()
        async with self._kb_lock:
            await loop.run_in_executor(None, self._kb.load)
        logger.info("Mech AI knowledge base: %s", self._kb.stats)

    # ── /create-mech-ai-channel ───────────────────────────────────────────────

    @app_commands.command(
        name="create-mech-ai-channel",
        description="Create a dedicated Mech Arena AI assistant channel in this server",
    )
    @app_commands.describe(channel_name="Channel name (default: mech-ai-assistant)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def create_mech_ai_channel(
        self,
        interaction: discord.Interaction,
        channel_name: str = "mech-ai-assistant",
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("Must be used inside a server.", ephemeral=True)
            return

        safe_name = channel_name.lower().strip().replace(" ", "-")[:80] or "mech-ai-assistant"

        try:
            channel = await interaction.guild.create_text_channel(
                name=safe_name,
                topic=(
                    "🤖 Ask me anything about Mech Arena! "
                    "Mechs · Weapons · Pilots · Maps · Builds · Strategies"
                ),
                reason="Mech Arena AI Assistant — created by /create-mech-ai-channel",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I don't have permission to create channels.", ephemeral=True
            )
            return
        except Exception as e:
            logger.error("create_mech_ai_channel: %s", e, exc_info=True)
            await interaction.followup.send(f"❌ Failed to create channel: {e}", ephemeral=True)
            return

        # Register channel
        self._ai_channels.add(channel.id)
        data = _load_channels()
        guild_key = str(interaction.guild.id)
        data.setdefault(guild_key, [])
        if str(channel.id) not in data[guild_key]:
            data[guild_key].append(str(channel.id))
        _save_channels(data)

        # Post welcome embed
        welcome = discord.Embed(
            title="🤖 Mech Arena AI Assistant",
            description=(
                "Welcome! I'm your dedicated Mech Arena expert. Ask me anything:\n\n"
                "🔧 **Mechs** — stats, abilities, tier lists, strengths & weaknesses\n"
                "💥 **Weapons** — DPS, range, reload, best combinations\n"
                "👨‍✈️ **Pilots** — abilities and which mechs they pair with\n"
                "💉 **Implants** — stat boosts and recommended setups\n"
                "🗺️ **Maps** — positioning, flanks, choke points\n"
                "⚔️ **Builds** — optimal loadouts for your playstyle\n"
                "🔄 **Counters** — how to beat specific mechs or comps\n"
                "📈 **Progression** — beginner tips to advanced tactics\n\n"
                "Just type your question — I'll search the knowledge base and answer!"
            ),
            color=discord.Color.from_rgb(0, 180, 255),
        )
        welcome.set_footer(text="Powered by Mech Arena AI • /mech-ai-stats to see coverage")
        await channel.send(embed=welcome)

        await interaction.followup.send(
            f"✅ AI channel created: {channel.mention}\n"
            "Users can now ask Mech Arena questions there.",
            ephemeral=True,
        )

    @create_mech_ai_channel.error
    async def _create_channel_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You need **Manage Channels** permission to use this command."
        else:
            logger.error("create_mech_ai_channel error: %s", error, exc_info=True)
            msg = "❌ An unexpected error occurred."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    # ── /delete-mech-ai-channel ───────────────────────────────────────────────

    @app_commands.command(
        name="delete-mech-ai-channel",
        description="Unregister a Mech Arena AI channel (optionally delete it)",
    )
    @app_commands.describe(
        channel="The AI channel to remove",
        delete_channel="Also delete the Discord channel? (default: No)",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def delete_mech_ai_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        delete_channel: bool = False,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("Must be used inside a server.", ephemeral=True)
            return

        if channel.id not in self._ai_channels:
            await interaction.followup.send(
                f"⚠️ {channel.mention} is not registered as a Mech AI channel.",
                ephemeral=True,
            )
            return

        self._ai_channels.discard(channel.id)
        self._conversations.pop(channel.id, None)

        data = _load_channels()
        guild_key = str(interaction.guild.id)
        if guild_key in data:
            data[guild_key] = [c for c in data[guild_key] if c != str(channel.id)]
        _save_channels(data)

        if delete_channel:
            try:
                await channel.delete(reason="Mech AI channel removed by admin")
                await interaction.followup.send(
                    "✅ AI channel unregistered and deleted.", ephemeral=True
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "✅ Unregistered, but I lack permission to delete the channel.",
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(
                f"✅ {channel.mention} unregistered as an AI channel. "
                "The channel itself was kept.",
                ephemeral=True,
            )

    @delete_mech_ai_channel.error
    async def _delete_channel_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You need **Manage Channels** permission."
        else:
            logger.error("delete_mech_ai_channel error: %s", error, exc_info=True)
            msg = "❌ An unexpected error occurred."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    # ── /reload-mech-knowledge ────────────────────────────────────────────────

    @app_commands.command(
        name="reload-mech-knowledge",
        description="Hot-reload the Mech Arena knowledge base from disk (no restart needed)",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reload_mech_knowledge(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        loop = asyncio.get_running_loop()
        async with self._kb_lock:
            await loop.run_in_executor(None, self._kb.reload)

        stats = self._kb.stats
        embed = discord.Embed(title="✅ Knowledge Base Reloaded", color=discord.Color.green())
        embed.add_field(name="📄 Files", value=str(stats["files"]), inline=True)
        embed.add_field(name="🧩 Chunks", value=str(stats["chunks"]), inline=True)
        embed.add_field(name="📝 Index Terms", value=str(stats["index_terms"]), inline=True)
        embed.add_field(
            name="📂 Categories",
            value=", ".join(stats["categories"]) or "none",
            inline=False,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @reload_mech_knowledge.error
    async def _reload_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            msg = "❌ You need **Manage Server** permission."
        else:
            logger.error("reload_mech_knowledge error: %s", error, exc_info=True)
            msg = "❌ An unexpected error occurred."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    # ── /mech-ai-stats ────────────────────────────────────────────────────────

    @app_commands.command(
        name="mech-ai-stats",
        description="Show Mech Arena AI knowledge base and channel statistics",
    )
    async def mech_ai_stats(self, interaction: discord.Interaction) -> None:
        stats = self._kb.stats
        guild_channel_count = 0
        if interaction.guild:
            data = _load_channels()
            guild_channel_count = len(data.get(str(interaction.guild.id), []))

        embed = discord.Embed(
            title="📊 Mech Arena AI Stats",
            color=discord.Color.from_rgb(0, 180, 255),
        )
        embed.add_field(name="📄 Knowledge Files", value=str(stats["files"]), inline=True)
        embed.add_field(name="🧩 Searchable Chunks", value=str(stats["chunks"]), inline=True)
        embed.add_field(name="📝 Index Terms", value=str(stats["index_terms"]), inline=True)
        embed.add_field(
            name="📂 Categories",
            value=", ".join(stats["categories"]) or "none",
            inline=False,
        )
        embed.add_field(
            name="📺 AI Channels (this server)",
            value=str(guild_channel_count),
            inline=True,
        )
        embed.add_field(
            name="💬 Active Conversations",
            value=str(len(self._conversations)),
            inline=True,
        )
        embed.add_field(
            name="✅ Index Status",
            value="Loaded ✓" if stats["loaded"] else "Not loaded",
            inline=True,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── on_message — RAG + AI reply ───────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not message.guild:
            return
        if message.channel.id not in self._ai_channels:
            return

        content = message.content.strip()
        if not content or len(content) < 2:
            return

        async with message.channel.typing():
            try:
                reply = await asyncio.wait_for(
                    self._rag_reply(
                        channel_id=message.channel.id,
                        username=message.author.display_name,
                        user_message=content,
                    ),
                    timeout=50,
                )
                embed = discord.Embed(
                    description=reply[:4000],
                    color=discord.Color.from_rgb(0, 180, 255),
                )
                embed.set_author(
                    name="🤖 Mech Arena AI",
                    icon_url=(
                        self.bot.user.display_avatar.url if self.bot.user else None
                    ),
                )
                embed.set_footer(
                    text="Answers grounded in knowledge base • /mech-ai-stats"
                )
                await message.reply(embed=embed, mention_author=False)

            except asyncio.TimeoutError:
                await message.reply(
                    "⏱️ I'm thinking too hard — please try again in a moment.",
                    mention_author=False,
                )
            except Exception as e:
                logger.error("Mech AI on_message error: %s", e, exc_info=True)
                await message.reply(
                    "❌ Something went wrong. Please try again.",
                    mention_author=False,
                )

    async def _rag_reply(
        self, channel_id: int, username: str, user_message: str
    ) -> str:
        """Full RAG pipeline: search KB → build prompt → call Groq → return reply."""
        if not mech_settings.groq_api_key:
            return (
                "❌ AI is not configured (`GROQ_API_KEY` missing). "
                "Please ask an admin to set this environment variable."
            )

        # 1. Retrieve relevant knowledge chunks (run in thread — CPU-bound BM25)
        loop = asyncio.get_running_loop()
        async with self._kb_lock:
            chunks = await loop.run_in_executor(
                None, lambda: self._kb.search(user_message, top_k=5)
            )

        if chunks:
            kb_context = "\n\n---\n\n".join(
                f"[{c.title}] ({c.source})\n{c.content}" for c in chunks
            )
        else:
            kb_context = (
                "No specific knowledge base entries matched this query. "
                "Answer from general Mech Arena knowledge if possible, "
                "but flag that the KB doesn't cover this topic."
            )

        # 2. Build conversation history (capped at last _MAX_HISTORY messages)
        history = self._conversations.setdefault(channel_id, [])

        groq_messages = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + f"\n\n=== KNOWLEDGE BASE EXCERPTS ===\n{kb_context}"
                    + "\n=== END KNOWLEDGE BASE ==="
                ),
            }
        ]
        groq_messages.extend(history[-_MAX_HISTORY:])
        groq_messages.append({"role": "user", "content": f"{username}: {user_message}"})

        # 3. Call Groq
        from groq import AsyncGroq

        client = AsyncGroq(api_key=mech_settings.groq_api_key, timeout=35.0)
        response = await client.chat.completions.create(
            model=mech_settings.groq_model,
            messages=groq_messages,
            max_tokens=900,
        )
        reply = response.choices[0].message.content or "I'm not sure — please try rephrasing."

        # 4. Persist conversation (rolling window)
        history.append({"role": "user", "content": f"{username}: {user_message}"})
        history.append({"role": "assistant", "content": reply})
        self._conversations[channel_id] = history[-_MAX_HISTORY:]

        return reply


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MechAICog(bot))
