import os

import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiEmojis, error_embed


class Mochi(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.prefix = os.getenv("COMMAND_PREFIX", os.getenv("BOT_PREFIX", "m!")).strip() or "m!"
        self.dev_guild_id = self._parse_int_env("DEV_GUILD_ID") or self._parse_int_env("GUILD_ID")
        super().__init__(
            command_prefix=commands.when_mentioned_or(self.prefix),
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

        admin_str = os.getenv("ADMIN_IDS", "")
        self.admins = [int(admin_id.strip()) for admin_id in admin_str.split(",") if admin_id.strip()]
        self.db = {}
        self.tree.on_error = self.handle_app_command_error

    @staticmethod
    def _parse_int_env(name):
        value = os.getenv(name, "").strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            print(f"Invalid {name}: {value!r}. Expected an integer Discord ID.")
            return None

    def get_user(self, uid):
        if uid not in self.db:
            self.db[uid] = {
                "wallet": 500,
                "bank": 0,
                "inventory": {},
                "last_daily": None,
            }
        return self.db[uid]

    async def setup_hook(self):
        cogs_path = os.path.join(os.path.dirname(__file__), "cogs")
        for filename in sorted(os.listdir(cogs_path)):
            if filename.endswith(".py") and not filename.startswith("_"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded cog: {filename}")

        if self.dev_guild_id:
            guild = discord.Object(id=self.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} slash commands to guild {self.dev_guild_id}.")
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global slash commands.")

        print(f"Registered slash commands: {[command.name for command in self.tree.get_commands()]}")

    async def on_ready(self):
        print(f"{self.user} is online.")
        print(f"Prefix: {self.prefix}")
        print(f"Admin IDs: {self.admins}")
        print(f"Dev guild: {self.dev_guild_id}")

    async def on_command_error(self, ctx, error):
        if hasattr(ctx.command, "on_error"):
            return

        original = getattr(error, "original", error)

        if isinstance(original, commands.CommandOnCooldown):
            embed = error_embed(
                f"{MochiEmojis.LOADING} Try again in `{original.retry_after:.1f}s`.",
                title="Cooldown Active",
            )
            await ctx.send(embed=embed)
            return

        if isinstance(original, commands.CheckFailure):
            embed = error_embed("You are not allowed to use that command.", title="Access Denied")
            await ctx.send(embed=embed)
            return

        if isinstance(original, commands.MissingRequiredArgument):
            embed = error_embed(
                f"Missing argument: `{original.param.name}`.",
                title="Missing Argument",
            )
            await ctx.send(embed=embed)
            return

        raise original

    async def handle_app_command_error(self, interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            embed = error_embed("You are not allowed to use that command.", title="Access Denied")
        else:
            embed = error_embed("That slash command ran into a problem.", title="Command Error")

        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

