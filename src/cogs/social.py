import datetime
import random

import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiColor, MochiEmojis, error_embed, info_embed, success_embed
from utils.game_data import CAREERS, COLLECTIBLES


class MoneyBagView(discord.ui.View):
    def __init__(self, social_cog):
        super().__init__(timeout=180)
        self.social_cog = social_cog
        self.message = None

    @discord.ui.button(label="Claim Money Bag", style=discord.ButtonStyle.success)
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        claimed, response_embed = self.social_cog.claim_drop(interaction.user.id)
        if claimed:
            if self.message is not None:
                for child in self.children:
                    child.disabled = True
                await self.message.edit(view=self)
        await interaction.response.send_message(embed=response_embed, ephemeral=False)


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _run_tax_event(self):
        events = self.bot.server_state["events"]
        now = self.bot.utcnow()
        last_tax = events["last_tax"]
        if last_tax and (now - last_tax).total_seconds() < 6 * 3600:
            return None

        taxed_players = []
        treasury_gain = 0
        for user_id, user in self.bot.db.items():
            total = user["wallet"] + user["bank"]
            if total > 1_000_000:
                tax = max(1, int(total * 0.05))
                wallet_tax = min(user["wallet"], tax)
                bank_tax = tax - wallet_tax
                user["wallet"] -= wallet_tax
                user["bank"] = max(0, user["bank"] - bank_tax)
                taxed_players.append((user_id, tax))
                treasury_gain += tax

        if taxed_players:
            self.bot.server_state["treasury"] += treasury_gain
            events["last_tax"] = now
            return taxed_players, treasury_gain
        return None

    def _career_name(self, user):
        index = max(0, min(user.get("career_level", 0), len(CAREERS) - 1))
        return CAREERS[index]["name"]

    def claim_drop(self, user_id: int):
        events = self.bot.server_state["events"]
        drop = events.get("active_drop")
        if not drop:
            return False, error_embed("There is no active money bag to claim right now.")
        if drop.get("claimed_by"):
            return False, error_embed("That money bag was already claimed.")

        user = self.bot.get_user(user_id)
        amount = drop["amount"]
        user["wallet"] += amount
        drop["claimed_by"] = user_id
        events["active_drop"] = None
        events["message_goal"] = random.randint(100, 500)
        events["messages_since_drop"] = 0
        return True, success_embed(
            f"{MochiEmojis.MONEY_BAG} You grabbed the drop and earned **{amount:,}** bits!",
            title="Money Bag Claimed",
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        events = self.bot.server_state["events"]
        if events.get("active_drop") is None:
            events["messages_since_drop"] += 1
            if events["messages_since_drop"] >= events["message_goal"]:
                amount = random.randint(500, 2500)
                events["active_drop"] = {
                    "channel_id": message.channel.id,
                    "amount": amount,
                    "claimed_by": None,
                }
                view = MoneyBagView(self)
                sent = await message.channel.send(
                    embed=info_embed(
                        f"{MochiEmojis.MONEY_BAG} A money bag worth **{amount:,}** bits just dropped.\n"
                        f"Click the button or type `{self.bot.prefix}claimdrop` first.",
                        title="World Drop",
                        color=MochiColor.GOLD,
                    ),
                    view=view,
                )
                view.message = sent

        tax_result = self._run_tax_event()
        if tax_result:
            taxed_players, treasury_gain = tax_result
            await message.channel.send(
                embed=info_embed(
                    f"{MochiEmojis.TAX} Tax Season struck **{len(taxed_players)}** wealthy players.\n"
                    f"Server treasury gained **{treasury_gain:,}** bits.",
                    title="Tax Season",
                    color=MochiColor.RED,
                )
            )

    @commands.hybrid_command(name="claimdrop", description="Claim the current money bag drop.")
    async def claimdrop(self, ctx):
        claimed, response_embed = self.claim_drop(ctx.author.id)
        await ctx.send(embed=response_embed)

    @commands.hybrid_command(name="daily", description="Claim your daily 500 bits.")
    async def daily(self, ctx):
        user = self.bot.get_user(ctx.author.id)
        now = self.bot.utcnow()
        last_claimed = user.get("last_daily")

        if last_claimed:
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

        user["last_daily"] = now
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
        visible_wallet = 0 if member.id != ctx.author.id and user["protection"].get("fake_wallet") else user["wallet"]

        embed = discord.Embed(
            title=f"{MochiEmojis.PROFILE} {member.display_name}'s Passport",
            color=MochiColor.PINK,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(
            name=f"{MochiEmojis.CURRENCY} Currency",
            value=f"Wallet: `{visible_wallet:,}`\nBank: `{user['bank']:,}`",
            inline=True,
        )
        embed.add_field(
            name=f"{MochiEmojis.WORK} Career",
            value=f"{self._career_name(user)}\nXP: `{user['work_xp']}`",
            inline=True,
        )

        visible_inventory = {
            item_id: amount
            for item_id, amount in user.get("inventory", {}).items()
            if item_id in COLLECTIBLES or item_id in {"padlock", "landmine", "fake_wallet", "golden_shield"}
        }
        inv_display = "\n".join(f"• {name.replace('_', ' ').title()}: x{amount}" for name, amount in visible_inventory.items())
        if not inv_display:
            inv_display = "Empty... puff of dust."

        embed.add_field(name=f"{MochiEmojis.BAG} Inventory", value=f"```\n{inv_display}\n```", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="treasury", description="View the server treasury and active bounty totals.")
    async def treasury(self, ctx):
        bounty_total = sum(self.bot.server_state["bounties"].values())
        active_drop = self.bot.server_state["events"].get("active_drop")
        drop_text = f"{active_drop['amount']:,} bits waiting" if active_drop else "No active money bag"
        await ctx.send(
            embed=info_embed(
                f"Treasury: **{self.bot.server_state['treasury']:,}** bits\n"
                f"Open bounties: **{bounty_total:,}** bits\n"
                f"Current drop: **{drop_text}**",
                title="Server Economy",
                color=MochiColor.GOLD,
            )
        )


async def setup(bot):
    await bot.add_cog(Social(bot))
