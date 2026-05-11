import random

import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiColor, MochiEmojis, error_embed, info_embed, success_embed


class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lottery_ticket_price = 200
        self.lottery_entries = []
        self.lottery_pot = 0
        self.last_lottery_winner = None

    @commands.hybrid_command(name="slots", description="Spin the slots with your bits.")
    @app_commands.describe(bet="How many bits you want to bet.")
    async def slots(self, ctx, bet: int):
        user = self.bot.get_user(ctx.author.id)
        if bet < 10 or bet > user["wallet"]:
            await ctx.send(embed=error_embed("Your bet must be at least 10 bits and within your wallet."))
            return

        user["wallet"] -= bet
        items = ["🍓", "🍵", "🍫", "💎"]
        rolls = [random.choice(items) for _ in range(3)]

        win = 0
        if rolls[0] == rolls[1] == rolls[2]:
            win = bet * 5
        elif rolls[0] == rolls[1] or rolls[1] == rolls[2]:
            win = bet * 2

        user["wallet"] += win
        result_name = f"{MochiEmojis.SUCCESS} Win" if win > 0 else f"{MochiEmojis.ERROR} Loss"
        result_text = f"You won **{win:,}** bits!" if win > 0 else f"You lost **{bet:,}** bits."

        embed = discord.Embed(
            title=f"{MochiEmojis.SLOTS} Mochi Slots",
            description=f"**[ {' | '.join(rolls)} ]**",
            color=MochiColor.PINK,
        )
        embed.add_field(name=result_name, value=result_text, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rob", description="Try to rob another member.")
    @app_commands.describe(member="The member you want to rob.")
    async def rob(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            await ctx.send(embed=error_embed("You cannot rob yourself."))
            return

        stealer = self.bot.get_user(ctx.author.id)
        victim = self.bot.get_user(member.id)

        if victim["wallet"] <= 0:
            await ctx.send(embed=error_embed("That member has no wallet cash to rob right now."))
            return

        if random.random() < 0.35:
            stolen = random.randint(1, victim["wallet"] // 2 or 1)
            victim["wallet"] -= stolen
            stealer["wallet"] += stolen
            embed = success_embed(
                f"{MochiEmojis.ROB} You robbed **{stolen:,}** bits from **{member.display_name}**!"
            )
        else:
            fine = min(150, stealer["wallet"])
            stealer["wallet"] -= fine
            embed = error_embed(f"You got caught and paid a **{fine:,}** bit fine.")

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="lottery", description="View the current lottery jackpot and recent winner.")
    async def lottery(self, ctx):
        unique_players = len(set(self.lottery_entries))
        last_winner_line = "No drawing has happened yet."
        if self.last_lottery_winner:
            last_winner_line = (
                f"<@{self.last_lottery_winner['user_id']}> won **{self.last_lottery_winner['prize']:,}** bits "
                f"with **{self.last_lottery_winner['tickets']}** ticket(s)."
            )

        embed = info_embed(
            f"{MochiEmojis.LOTTERY} Ticket price: **{self.lottery_ticket_price:,}** bits\n"
            f"{MochiEmojis.CURRENCY} Current jackpot: **{self.lottery_pot:,}** bits\n"
            f"{MochiEmojis.PAGE} Tickets sold: **{len(self.lottery_entries)}**\n"
            f"{MochiEmojis.PROFILE} Players entered: **{unique_players}**\n\n"
            f"{MochiEmojis.TROPHY} Last winner: {last_winner_line}",
            title="Lottery Board",
            color=MochiColor.GOLD,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buyticket", description="Buy lottery tickets with wallet cash.")
    @app_commands.describe(quantity="How many lottery tickets to buy.")
    async def buyticket(self, ctx, quantity: int = 1):
        if quantity <= 0:
            await ctx.send(embed=error_embed("Ticket quantity must be at least 1."))
            return

        user = self.bot.get_user(ctx.author.id)
        total_cost = self.lottery_ticket_price * quantity
        if user["wallet"] < total_cost:
            await ctx.send(embed=error_embed("You do not have enough wallet bits to buy that many tickets."))
            return

        user["wallet"] -= total_cost
        self.lottery_pot += total_cost
        self.lottery_entries.extend([ctx.author.id] * quantity)

        embed = success_embed(
            f"{MochiEmojis.LOTTERY} Bought **{quantity}** ticket(s) for **{total_cost:,}** bits.\n"
            f"{MochiEmojis.CURRENCY} Jackpot is now **{self.lottery_pot:,}** bits.",
            title="Tickets Purchased",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="drawlottery", description="Draw a winner from the current lottery pool.")
    async def drawlottery(self, ctx):
        unique_players = set(self.lottery_entries)
        if len(self.lottery_entries) == 0:
            await ctx.send(embed=error_embed("No lottery tickets have been bought yet."))
            return
        if len(unique_players) < 2:
            await ctx.send(embed=error_embed("At least two different players need tickets before drawing."))
            return

        winner_id = random.choice(self.lottery_entries)
        winner = self.bot.get_user(winner_id)
        ticket_count = self.lottery_entries.count(winner_id)
        prize = self.lottery_pot
        winner["wallet"] += prize
        self.last_lottery_winner = {"user_id": winner_id, "prize": prize, "tickets": ticket_count}

        self.lottery_entries.clear()
        self.lottery_pot = 0

        embed = success_embed(
            f"{MochiEmojis.TROPHY} <@{winner_id}> won the lottery!\n"
            f"Prize: **{prize:,}** bits\n"
            f"Winning tickets owned: **{ticket_count}**",
            title="Lottery Draw Complete",
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Games(bot))
