import random

import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiColor, MochiEmojis, error_embed, success_embed


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", aliases=["bal"], description="Check your wallet and bank balance.")
    @app_commands.describe(member="The member whose balance you want to view.")
    async def balance(self, ctx, member: discord.Member | None = None):
        member = member or ctx.author
        user = self.bot.get_user(member.id)

        embed = discord.Embed(
            title=f"{MochiEmojis.DAILY} {member.display_name}'s Pantry",
            color=MochiColor.PINK,
        )
        embed.add_field(
            name=f"{MochiEmojis.CURRENCY} Wallet",
            value=f"**{user['wallet']:,}** bits",
            inline=True,
        )
        embed.add_field(
            name=f"{MochiEmojis.BANK} Bank",
            value=f"**{user['bank']:,}** bits",
            inline=True,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="deposit",
        aliases=["dep"],
        description="Move bits from your wallet into the bank.",
    )
    @app_commands.describe(amount="How many bits to deposit.")
    async def deposit(self, ctx, amount: int):
        user = self.bot.get_user(ctx.author.id)
        if amount <= 0:
            await ctx.send(embed=error_embed("Deposit amount must be greater than zero."))
            return

        if user["wallet"] < amount:
            await ctx.send(embed=error_embed("You do not have that many bits in your wallet."))
            return

        user["wallet"] -= amount
        user["bank"] += amount

        embed = success_embed(
            f"{MochiEmojis.BANK} Deposited **{amount:,}** bits.\n"
            f"{MochiEmojis.CURRENCY} Wallet: **{user['wallet']:,}**\n"
            f"{MochiEmojis.BANK} Bank: **{user['bank']:,}**",
            title="Deposit Complete",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="withdraw",
        aliases=["with"],
        description="Move bits from your bank into your wallet.",
    )
    @app_commands.describe(amount="How many bits to withdraw.")
    async def withdraw(self, ctx, amount: int):
        user = self.bot.get_user(ctx.author.id)
        if amount <= 0:
            await ctx.send(embed=error_embed("Withdraw amount must be greater than zero."))
            return

        if user["bank"] < amount:
            await ctx.send(embed=error_embed("You do not have that many bits in the bank."))
            return

        user["bank"] -= amount
        user["wallet"] += amount

        embed = success_embed(
            f"{MochiEmojis.CURRENCY} Withdrew **{amount:,}** bits.\n"
            f"{MochiEmojis.CURRENCY} Wallet: **{user['wallet']:,}**\n"
            f"{MochiEmojis.BANK} Bank: **{user['bank']:,}**",
            title="Withdrawal Complete",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="work", description="Work a shift and earn some bits.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def work(self, ctx):
        income = random.randint(100, 300)
        user = self.bot.get_user(ctx.author.id)
        user["wallet"] += income

        embed = success_embed(
            f"{MochiEmojis.WORK} You prepared matcha and earned **{income:,}** bits!"
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="gift", description="Gift bits to another member.")
    @app_commands.describe(amount="How many bits to gift.", member="The member receiving the gift.")
    async def gift(self, ctx, amount: int, member: discord.Member):
        if amount <= 0 or member.id == ctx.author.id:
            await ctx.send(embed=error_embed("Choose a positive amount and a different member."))
            return

        sender = self.bot.get_user(ctx.author.id)
        if sender["wallet"] < amount:
            await ctx.send(embed=error_embed("You do not have enough bits for that gift."))
            return

        receiver = self.bot.get_user(member.id)
        sender["wallet"] -= amount
        receiver["wallet"] += amount

        embed = success_embed(
            f"{MochiEmojis.GIFT} {ctx.author.mention} gifted **{amount:,}** bits to {member.mention}!"
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))
