import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiColor, MochiEmojis, error_embed, success_embed


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    @commands.hybrid_command(name="daily", description="Claim your daily 500 bits.")
    async def daily(self, ctx):
        user_id = ctx.author.id
        now = datetime.datetime.now(datetime.timezone.utc)

        if user_id in self.cooldowns:
            last_claimed = self.cooldowns[user_id]
            delta = now - last_claimed

            if delta.total_seconds() < 86400:
                remaining = 86400 - delta.total_seconds()
                hours, remainder = divmod(int(remaining), 3600)
                minutes, _ = divmod(remainder, 60)
                embed = error_embed(
                    f"{MochiEmojis.LOADING} Next daily in **{hours}h {minutes}m**.",
                    title="Patience, Mochi",
                )
                await ctx.send(embed=embed)
                return

        self.cooldowns[user_id] = now
        user = self.bot.get_user(user_id)
        user["wallet"] += 500

        embed = success_embed(
            f"{MochiEmojis.DAILY} You found **500** bits in your pantry!",
            title="Daily Reward",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="profile", aliases=["p"], description="View a member profile and inventory.")
    @app_commands.describe(member="The member whose profile you want to view.")
    async def profile(self, ctx, member: discord.Member | None = None):
        member = member or ctx.author
        user = self.bot.get_user(member.id)

        embed = discord.Embed(
            title=f"{MochiEmojis.PROFILE} {member.display_name}'s Passport",
            color=MochiColor.PINK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name=f"{MochiEmojis.CURRENCY} Currency",
            value=f"Wallet: `{user['wallet']:,}`\nBank: `{user['bank']:,}`",
            inline=True,
        )

        inv = user.get("inventory", {})
        inv_display = "\n".join(f"• {name.title()}: x{amount}" for name, amount in inv.items())
        if not inv_display:
            inv_display = "Empty... 💨"

        embed.add_field(
            name=f"{MochiEmojis.BAG} Inventory",
            value=f"```\n{inv_display}\n```",
            inline=True,
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Social(bot))
