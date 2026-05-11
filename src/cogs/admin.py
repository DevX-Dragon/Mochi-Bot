import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiEmojis, success_embed
from utils.checks import admin_only, app_admin_only


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="addmoney", description="Add bits to a user's wallet.")
    @app_commands.describe(amount="How many bits to add.", member="The target member.")
    @admin_only()
    @app_admin_only()
    async def addmoney(self, ctx, amount: int, member: discord.Member | None = None):
        target = member or ctx.author
        user = self.bot.get_user(target.id)
        user["wallet"] += amount

        embed = success_embed(
            f"{MochiEmojis.ADMIN} Added **{amount:,}** bits to **{target.display_name}**.",
            title="Admin Action",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="reload", description="Reload a cog by name.")
    @app_commands.describe(cog="The cog filename without .py, like economy or social.")
    @admin_only()
    @app_admin_only()
    async def reload(self, ctx, cog: str):
        await self.bot.reload_extension(f"cogs.{cog}")
        embed = success_embed(f"Reloaded `{cog}` successfully.", title="Cog Reloaded")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
