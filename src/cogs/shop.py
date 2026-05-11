import math

import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiColor, MochiEmojis, error_embed, info_embed, success_embed


int, page: int, total_pages: int):
        super().__init__(timeout=120)
        self.shop_cog = shop_cog
        self.owner_id = owner_id
        self.page = page
        self.total_pages = total_pages
        self.message = None
        self._sync_buttons()

    def _sync_buttons(self):
        self.previous_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.total_pages

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                embed=error_embed("Only the user who opened this shop menu can flip its pages."),
                ephemeral=True,
            )
            return False
        return True

    async def _refresh(self, interaction: discord.Interaction):
        embed, _ = self.shop_cog._build_shop_embed(self.page)
        self._sync_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message is not None:
            await self.message.edit(view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        await self._refresh(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        await self._refresh(interaction)


class Shop(commands.Cog):
    PAGE_SIZE = 5

    def __init__(self, bot):
        self.bot = bot
        self.next_trade_id = 1
        self.pending_trades = {}
        self.items = {
            "matcha": {
                "name": "Matcha Powder",
                "cost": 200,
                "desc": "A basic ingredient for soft green desserts.",
                "category": "Pantry",
            },
            "azuki": {
                "name": "Azuki Beans",
                "cost": 260,
                "desc": "Sweet red bean filling for classic mochi.",
                "category": "Pantry",
            },
            "rice_flour": {
                "name": "Rice Flour",
                "cost": 320,
                "desc": "The chewy backbone of every mochi batch.",
                "category": "Pantry",
            },
            "strawberry": {
                "name": "Strawberry Basket",
                "cost": 420,
                "desc": "Bright fruit filling for fresh daifuku.",
                "category": "Produce",
            },
            "cream": {
                "name": "Whipped Cream",
                "cost": 500,
                "desc": "Cloud-soft topping for luxe treats.",
                "category": "Dairy",
            },
            "boba": {
                "name": "Boba Pearls",
                "cost": 650,
                "desc": "Chewy pearls for drink and dessert experiments.",
                "category": "Cafe",
            },
            "sakura": {
                "name": "Sakura Petals",
                "cost": 900,
                "desc": "Fragrant petals that make seasonal sweets feel rare.",
                "category": "Seasonal",
            },
            "yuzu": {
                "name": "Yuzu Zest",
                "cost": 1200,
                "desc": "Citrus sparkle for a sharp premium finish.",
                "category": "Seasonal",
            },
            "gold_leaf": {
                "name": "Gold Leaf",
                "cost": 5000,
                "desc": "Pure luxury for over-the-top presentation.",
                "category": "Luxury",
            },
            "moon_sugar": {
                "name": "Moon Sugar",
                "cost": 7600,
                "desc": "A glowing sweetener whispered about in dessert lore.",
                "category": "Luxury",
            },
            "dragonfruit": {
                "name": "Dragonfruit Slice",
                "cost": 2100,
                "desc": "Vivid fruit with a dramatic look and mellow taste.",
                "category": "Produce",
            },
            "black_sesame": {
                "name": "Black Sesame Paste",
                "cost": 1400,
                "desc": "Nutty filling with a toasty finish.",
                "category": "Pantry",
            },
        }
        self.item_order = list(self.items.keys())

    def _build_shop_embed(self, page: int):
        total_pages = math.ceil(len(self.item_order) / self.PAGE_SIZE)
        page = max(1, min(page, total_pages))
        start = (page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE

        embed = info_embed(
            "Treat yourself to something nice. Use `/buy item_id quantity` or your prefix equivalent.",
            title=f"{MochiEmojis.SHOP} Mochi Shop",
        )

        for item_id in self.item_order[start:end]:
            info = self.items[item_id]
            embed.add_field(
                name=f"{info['name']} • {info['cost']:,} bits",
                value=f"`{item_id}` • {info['category']}\n{info['desc']}",
                inline=False,
            )

        embed.set_footer(text=f"{MochiEmojis.PAGE} Page {page}/{total_pages}")
        return embed, total_pages

    def _format_trade_side(self, *, item_id=None, amount=0, bits=0):
        parts = []
        if item_id and amount > 0:
            item_name = self.items[item_id]["name"] if item_id in self.items else item_id
            parts.append(f"{amount}x {item_name}")
        if bits > 0:
            parts.append(f"{bits:,} bits")
        return ", ".join(parts) if parts else "nothing"

    @commands.hybrid_command(name="shop", description="Browse the Mochi shop.")
    @app_commands.describe(page="The shop page to view.")
    async def shop(self, ctx, page: int = 1):
        embed, total_pages = self._build_shop_embed(page)
        current_page = max(1, min(page, total_pages))
        view = ShopPaginationView(self, ctx.author.id, current_page, total_pages)
        if page < 1 or page > total_pages:
            embed.description = (
                f"{embed.description}\n\n{MochiEmojis.ERROR} Page `{page}` is out of range, "
                f"so I showed page `{max(1, min(page, total_pages))}` instead."
            )
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(name="buy", description="Buy an item from the shop.")
    @app_commands.describe(
        item_id="The item id to buy, like matcha or gold_leaf.",
        quantity="How many copies you want to buy.",
    )
    async def buy(self, ctx, item_id: str, quantity: int = 1):
        item_id = item_id.lower()
        if item_id not in self.items:
            await ctx.send(embed=error_embed("We do not sell that item here."))
            return
        if quantity <= 0:
            await ctx.send(embed=error_embed("Quantity must be at least 1."))
            return

        user = self.bot.get_user(ctx.author.id)
        cost = self.items[item_id]["cost"] * quantity
        if user["wallet"] < cost:
            await ctx.send(embed=error_embed("You do not have enough bits for that purchase."))
            return

        user["wallet"] -= cost
        inventory = user["inventory"]
        inventory[item_id] = inventory.get(item_id, 0) + quantity

        embed = success_embed(
            f"Bought **{quantity}x {self.items[item_id]['name']}** for **{cost:,}** bits.\n"
            f"{MochiEmojis.CURRENCY} Wallet left: **{user['wallet']:,}** bits",
            title="Purchase Complete",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="trade", description="Create a trade offer for another member.")
    @app_commands.describe(
        member="The member you want to trade with.",
        offer_item="The item you are offering.",
        offer_amount="How many of that item you are offering.",
        request_item="The item you want back, if any.",
        request_amount="How many of that requested item you want.",
        request_bits="How many bits you want the other member to pay.",
    )
    async def trade(
        self,
        ctx,
        member: discord.Member,
        offer_item: str,
        offer_amount: int,
        request_item: str | None = None,
        request_amount: int = 0,
        request_bits: int = 0,
    ):
        offer_item = offer_item.lower()
        request_item = request_item.lower() if request_item else None

        if member.id == ctx.author.id:
            await ctx.send(embed=error_embed("You cannot trade with yourself."))
            return
        if offer_item not in self.items:
            await ctx.send(embed=error_embed("Your offered item is not sold in the Mochi shop."))
            return
        if request_item and request_item not in self.items:
            await ctx.send(embed=error_embed("The requested item is not sold in the Mochi shop."))
            return
        if offer_amount <= 0:
            await ctx.send(embed=error_embed("Offer amount must be at least 1."))
            return
        if request_amount < 0 or request_bits < 0:
            await ctx.send(embed=error_embed("Requested amounts cannot be negative."))
            return
        if not request_item and request_bits <= 0:
            await ctx.send(
                embed=error_embed("Add a requested item or a requested bit amount so the trade has terms.")
            )
            return
        if request_item and request_amount <= 0:
            await ctx.send(embed=error_embed("Requested item trades need a requested amount of at least 1."))
            return

        sender = self.bot.get_user(ctx.author.id)
        if sender["inventory"].get(offer_item, 0) < offer_amount:
            await ctx.send(embed=error_embed("You do not own enough of that item to offer it."))
            return

        trade_id = self.next_trade_id
        self.next_trade_id += 1
        self.pending_trades[trade_id] = {
            "sender_id": ctx.author.id,
            "recipient_id": member.id,
            "offer_item": offer_item,
            "offer_amount": offer_amount,
            "request_item": request_item,
            "request_amount": request_amount,
            "request_bits": request_bits,
        }

        sender_side = self._format_trade_side(item_id=offer_item, amount=offer_amount)
        recipient_side = self._format_trade_side(
            item_id=request_item,
            amount=request_amount,
            bits=request_bits,
        )
        embed = info_embed(
            f"{ctx.author.mention} offered **{sender_side}** to {member.mention}\n"
            f"in exchange for **{recipient_side}**.\n\n"
            f"Use `/tradeaccept {trade_id}` or `{self.bot.prefix}tradeaccept {trade_id}` to accept.",
            title=f"{MochiEmojis.TRADE} Trade Offer #{trade_id}",
            color=MochiColor.GOLD,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="tradeaccept", description="Accept a pending trade offer.")
    @app_commands.describe(trade_id="The trade id to accept.")
    async def tradeaccept(self, ctx, trade_id: int):
        trade = self.pending_trades.get(trade_id)
        if not trade:
            await ctx.send(embed=error_embed("That trade does not exist anymore."))
            return
        if trade["recipient_id"] != ctx.author.id:
            await ctx.send(embed=error_embed("Only the invited trade partner can accept this trade."))
            return

        sender = self.bot.get_user(trade["sender_id"])
        recipient = self.bot.get_user(trade["recipient_id"])
        if sender["inventory"].get(trade["offer_item"], 0) < trade["offer_amount"]:
            self.pending_trades.pop(trade_id, None)
            await ctx.send(embed=error_embed("The sender no longer has the offered items. The trade was canceled."))
            return
        if trade["request_item"] and recipient["inventory"].get(trade["request_item"], 0) < trade["request_amount"]:
            await ctx.send(embed=error_embed("You no longer have the requested item quantity."))
            return
        if recipient["wallet"] < trade["request_bits"]:
            await ctx.send(embed=error_embed("You do not have enough wallet bits to complete this trade."))
            return

        sender["inventory"][trade["offer_item"]] -= trade["offer_amount"]
        if sender["inventory"][trade["offer_item"]] <= 0:
            sender["inventory"].pop(trade["offer_item"], None)
        recipient["inventory"][trade["offer_item"]] = (
            recipient["inventory"].get(trade["offer_item"], 0) + trade["offer_amount"]
        )

        if trade["request_item"]:
            recipient["inventory"][trade["request_item"]] -= trade["request_amount"]
            if recipient["inventory"][trade["request_item"]] <= 0:
                recipient["inventory"].pop(trade["request_item"], None)
            sender["inventory"][trade["request_item"]] = (
                sender["inventory"].get(trade["request_item"], 0) + trade["request_amount"]
            )

        if trade["request_bits"] > 0:
            recipient["wallet"] -= trade["request_bits"]
            sender["wallet"] += trade["request_bits"]

        self.pending_trades.pop(trade_id, None)

        sender_member = ctx.guild.get_member(trade["sender_id"]) if ctx.guild else None
        sender_name = sender_member.mention if sender_member else f"<@{trade['sender_id']}>"
        embed = success_embed(
            f"{ctx.author.mention} accepted trade **#{trade_id}** from {sender_name}.\n"
            f"{MochiEmojis.TRADE} Deal completed successfully.",
            title="Trade Complete",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="tradecancel", description="Cancel one of your outgoing trade offers.")
    @app_commands.describe(trade_id="The trade id to cancel.")
    async def tradecancel(self, ctx, trade_id: int):
        trade = self.pending_trades.get(trade_id)
        if not trade:
            await ctx.send(embed=error_embed("That trade does not exist anymore."))
            return
        if trade["sender_id"] != ctx.author.id:
            await ctx.send(embed=error_embed("Only the person who created the trade can cancel it."))
            return

        self.pending_trades.pop(trade_id, None)
        await ctx.send(embed=success_embed(f"Canceled trade **#{trade_id}**.", title="Trade Canceled"))

    @commands.hybrid_command(name="trades", description="List pending trades involving you.")
    async def trades(self, ctx):
        related_trades = [
            (trade_id, trade)
            for trade_id, trade in self.pending_trades.items()
            if ctx.author.id in {trade["sender_id"], trade["recipient_id"]}
        ]
        if not related_trades:
            await ctx.send(embed=info_embed("You do not have any pending trades right now.", title="No Trades"))
            return

        embed = info_embed(
            "Incoming and outgoing offers tied to your account.",
            title=f"{MochiEmojis.TRADE} Pending Trades",
            color=MochiColor.GOLD,
        )
        for trade_id, trade in related_trades[:8]:
            direction = "Outgoing" if trade["sender_id"] == ctx.author.id else "Incoming"
            partner_id = trade["recipient_id"] if direction == "Outgoing" else trade["sender_id"]
            partner = ctx.guild.get_member(partner_id) if ctx.guild else None
            partner_name = partner.display_name if partner else str(partner_id)
            sender_side = self._format_trade_side(item_id=trade["offer_item"], amount=trade["offer_amount"])
            recipient_side = self._format_trade_side(
                item_id=trade["request_item"],
                amount=trade["request_amount"],
                bits=trade["request_bits"],
            )
            embed.add_field(
                name=f"#{trade_id} • {direction} • {partner_name}",
                value=f"Offer: {sender_side}\nRequest: {recipient_side}",
                inline=False,
            )

        if len(related_trades) > 8:
            embed.set_footer(text="Showing the first 8 pending trades.")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Shop(bot))

