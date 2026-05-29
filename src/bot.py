import os
from datetime import datetime, timedelta, timezone

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
        self.server_state = {
            "treasury": 0,
            "bounties": {},
            "market": {
                "last_refresh": None,
                "coins": {
                    "mochi": {"name": "Mochi Coin", "price": 120, "min_price": 40, "max_price": 420},
                    "matcha": {"name": "Matcha Coin", "price": 260, "min_price": 80, "max_price": 850},
                    "boba": {"name": "Boba Coin", "price": 520, "min_price": 140, "max_price": 1600},
                },
            },
            "events": {
                "message_goal": 180,
                "messages_since_drop": 0,
                "active_drop": None,
                "last_tax": None,
            },
        }
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
                "career_level": 0,
                "work_xp": 0,
                "skills": [],
                "passive_income": {},
                "last_passive_claim": None,
                "bank_interest_at": None,
                "stats": {
                    "work_successes": 0,
                    "work_failures": 0,
                    "rob_successes": 0,
                    "rob_failures": 0,
                    "career_earnings": 0,
                },
                "cooldowns": {
                    "hospital_until": None,
                },
                "protection": {
                    "shield_charges": 0,
                    "fake_wallet": False,
                },
                "stocks": {},
            }
        user = self.db[uid]
        user.setdefault("inventory", {})
        user.setdefault("skills", [])
        user.setdefault("passive_income", {})
        user.setdefault("stocks", {})
        user.setdefault(
            "stats",
            {
                "work_successes": 0,
                "work_failures": 0,
                "rob_successes": 0,
                "rob_failures": 0,
                "career_earnings": 0,
            },
        )
        user.setdefault("cooldowns", {"hospital_until": None})
        user.setdefault("protection", {"shield_charges": 0, "fake_wallet": False})
        user.setdefault("career_level", 0)
        user.setdefault("work_xp", 0)
        user.setdefault("last_passive_claim", None)
        user.setdefault("bank_interest_at", None)
        user.setdefault("last_daily", None)
        return user

    def utcnow(self):
        return datetime.now(timezone.utc)

    def add_item(self, user, item_id: str, amount: int = 1):
        inventory = user["inventory"]
        inventory[item_id] = inventory.get(item_id, 0) + amount
        if inventory[item_id] <= 0:
            inventory.pop(item_id, None)

    def apply_passive_income(self, user):
        now = self.utcnow()
        last_claim = user.get("last_passive_claim")
        if last_claim is None:
            user["last_passive_claim"] = now
            return 0

        elapsed_seconds = max(0, (now - last_claim).total_seconds())
        hours_elapsed = int(elapsed_seconds // 3600)
        if hours_elapsed <= 0:
            return 0

        hourly_income = 0
        for business in user.get("passive_income", {}).values():
            hourly_income += business.get("hourly_income", 0) * business.get("count", 0)

        payout = hourly_income * hours_elapsed
        if payout > 0:
            user["wallet"] += payout
        user["last_passive_claim"] = last_claim + timedelta(hours=hours_elapsed)
        return payout

    def apply_bank_interest(self, user):
        now = self.utcnow()
        last_interest = user.get("bank_interest_at")
        if last_interest is None:
            user["bank_interest_at"] = now
            return 0

        elapsed_seconds = max(0, (now - last_interest).total_seconds())
        weeks_elapsed = int(elapsed_seconds // (7 * 24 * 3600))
        if weeks_elapsed <= 0 or user["bank"] <= 0:
            return 0

        total_interest = 0
        for _ in range(weeks_elapsed):
            rate = 0.01 if user["bank"] < 50000 else 0.02
            interest = max(1, int(user["bank"] * rate))
            user["bank"] += interest
            total_interest += interest

        user["bank_interest_at"] = last_interest + timedelta(weeks=weeks_elapsed)
        return total_interest

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
