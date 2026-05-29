import random
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from utils.assets import MochiColor, MochiEmojis, error_embed, info_embed, success_embed
from utils.game_data import BUSINESSES, CAREERS, COLLECTIBLES, SHOP_ITEMS, SKILLS


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _current_career(self, user):
        index = max(0, min(user.get("career_level", 0), len(CAREERS) - 1))
        return CAREERS[index]

    def _next_career(self, user):
        index = user.get("career_level", 0) + 1
        if index >= len(CAREERS):
            return None
        return CAREERS[index]

    def _ensure_market(self):
        market = self.bot.server_state["market"]
        now = self.bot.utcnow()
        last_refresh = market["last_refresh"]
        if last_refresh is None:
            market["last_refresh"] = now
            return

        elapsed = now - last_refresh
        cycles = int(elapsed.total_seconds() // (30 * 60))
        if cycles <= 0:
            return

        for _ in range(cycles):
            for coin in market["coins"].values():
                movement = random.uniform(-0.2, 0.22)
                next_price = int(coin["price"] * (1 + movement))
                coin["price"] = max(coin["min_price"], min(coin["max_price"], next_price))

        market["last_refresh"] = last_refresh + timedelta(minutes=30 * cycles)

    def _format_inventory(self, inventory):
        if not inventory:
            return "Empty... puff of dust."
        return "\n".join(f"- {item_id.replace('_', ' ').title()}: x{amount}" for item_id, amount in inventory.items())

    def _format_named_counts(self, entries):
        if not entries:
            return "None"
        return "\n".join(f"- {name}: x{amount}" for name, amount in entries)

    def _format_stocks(self, stocks):
        owned_stocks = [(coin_id.upper(), shares) for coin_id, shares in stocks.items() if shares > 0]
        if not owned_stocks:
            return "None"
        return "\n".join(f"- {coin}: {shares} shares" for coin, shares in owned_stocks)

    async def _run_work_minigame(self, ctx):
        challenge_type = random.choice(["typing", "math"])
        if challenge_type == "typing":
            word = random.choice(["mochi", "career", "bitstorm", "treasury", "matcha", "skyscraper"])
            prompt = info_embed(
                f"Type **{word}** in chat within **5 seconds** to finish your shift.",
                title=f"{MochiEmojis.WORK} Work Challenge",
            )
            await ctx.send(embed=prompt)

            def check(message):
                return (
                    message.author.id == ctx.author.id
                    and message.channel.id == ctx.channel.id
                    and message.content.strip().lower() == word.lower()
                )

            try:
                await self.bot.wait_for("message", timeout=5, check=check)
                return True, f"Typed `{word}` fast enough."
            except TimeoutError:
                return False, f"You missed the **{word}** prompt."

        left = random.randint(3, 20)
        right = random.randint(4, 25)
        answer = str(left + right)
        prompt = info_embed(
            f"Solve **{left} + {right}** in chat within **5 seconds**.",
            title=f"{MochiEmojis.WORK} Work Challenge",
        )
        await ctx.send(embed=prompt)

        def check(message):
            return (
                message.author.id == ctx.author.id
                and message.channel.id == ctx.channel.id
                and message.content.strip() == answer
            )

        try:
            await self.bot.wait_for("message", timeout=5, check=check)
            return True, f"Solved `{left} + {right}` correctly."
        except TimeoutError:
            return False, "The math shift timer expired."

    def _roll_loot(self, career):
        drops = []
        for item_id, chance in career.get("loot_table", []):
            if random.random() <= chance:
                drops.append(item_id)
        return drops

    @commands.hybrid_command(name="balance", aliases=["bal"], description="Check your wallet and bank balance.")
    @app_commands.describe(member="The member whose balance you want to view.")
    async def balance(self, ctx, member: discord.Member | None = None):
        member = member or ctx.author
        user = self.bot.get_user(member.id)
        passive = self.bot.apply_passive_income(user)
        interest = self.bot.apply_bank_interest(user)

        embed = discord.Embed(
            title=f"{MochiEmojis.DAILY} {member.display_name}'s Pantry",
            color=MochiColor.PINK,
        )
        embed.add_field(name=f"{MochiEmojis.CURRENCY} Wallet", value=f"**{user['wallet']:,}** bits", inline=True)
        embed.add_field(name=f"{MochiEmojis.BANK} Bank", value=f"**{user['bank']:,}** bits", inline=True)
        embed.add_field(
            name=f"{MochiEmojis.BUSINESS} Passive Income",
            value=f"Collected now: **{passive:,}**\nInterest now: **{interest:,}**",
            inline=False,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="career", description="View your current job and promotion goals.")
    async def career(self, ctx):
        user = self.bot.get_user(ctx.author.id)
        current = self._current_career(user)
        next_job = self._next_career(user)
        skill_names = ", ".join(SKILLS[skill]["name"] for skill in user["skills"]) if user["skills"] else "None"

        description = (
            f"Current job: **{current['name']}**\n"
            f"XP: **{user['work_xp']}**\n"
            f"Base pay: **{current['base_pay']:,}** bits\n"
            f"Skills: **{skill_names}**"
        )
        if next_job:
            description += (
                f"\n\nNext promotion: **{next_job['name']}**"
                f"\nNeeds XP: **{next_job['xp_required']}**"
                f"\nNeeds skill: **{SKILLS[next_job['skill_required']]['name']}**"
            )
        else:
            description += "\n\nYou are already at the top of the ladder."

        await ctx.send(embed=info_embed(description, title=f"{MochiEmojis.WORK} Career Board", color=MochiColor.GOLD))

    @commands.hybrid_command(name="promote", description="Try to move up to the next career level.")
    async def promote(self, ctx):
        user = self.bot.get_user(ctx.author.id)
        next_job = self._next_career(user)
        if next_job is None:
            await ctx.send(embed=error_embed("You are already a CEO. There is nowhere higher to go."))
            return

        if user["work_xp"] < next_job["xp_required"]:
            await ctx.send(embed=error_embed("You do not have enough work XP for that promotion yet."))
            return
        if next_job["skill_required"] and next_job["skill_required"] not in user["skills"]:
            await ctx.send(
                embed=error_embed(
                    f"You still need the **{SKILLS[next_job['skill_required']]['name']}** skill for that promotion."
                )
            )
            return

        user["career_level"] += 1
        await ctx.send(
            embed=success_embed(
                f"{MochiEmojis.TROPHY} Promoted to **{next_job['name']}**.",
                title="Promotion Complete",
            )
        )

    @commands.hybrid_command(
        name="deposit",
        aliases=["dep"],
        description="Move bits from your wallet into the bank.",
    )
    @app_commands.describe(amount="How many bits to deposit.")
    async def deposit(self, ctx, amount: int):
        user = self.bot.get_user(ctx.author.id)
        self.bot.apply_bank_interest(user)
        if amount <= 0:
            await ctx.send(embed=error_embed("Deposit amount must be greater than zero."))
            return

        if user["wallet"] < amount:
            await ctx.send(embed=error_embed("You do not have that many bits in your wallet."))
            return

        user["wallet"] -= amount
        user["bank"] += amount
        if user["bank_interest_at"] is None:
            user["bank_interest_at"] = self.bot.utcnow()

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
        interest = self.bot.apply_bank_interest(user)
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
            f"{MochiEmojis.BANK} Bank: **{user['bank']:,}**\n"
            f"{MochiEmojis.TAX} Interest applied now: **{interest:,}**",
            title="Withdrawal Complete",
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="work", description="Complete a mini-game shift and earn career income.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def work(self, ctx):
        user = self.bot.get_user(ctx.author.id)
        hospital_until = user["cooldowns"].get("hospital_until")
        now = self.bot.utcnow()
        if hospital_until and hospital_until > now:
            remaining = hospital_until - now
            minutes = int(remaining.total_seconds() // 60)
            await ctx.send(
                embed=error_embed(
                    f"{MochiEmojis.HOSPITAL} You are in the hospital for another **{minutes} minutes**."
                )
            )
            return

        success, note = await self._run_work_minigame(ctx)
        career = self._current_career(user)
        if not success:
            user["stats"]["work_failures"] += 1
            await ctx.send(embed=error_embed(f"{note}\nNo payout this time.", title="Shift Failed"))
            return

        payout = career["base_pay"] + random.randint(0, max(60, career["base_pay"] // 3))
        xp_gain = random.randint(18, 35)
        user["wallet"] += payout
        user["work_xp"] += xp_gain
        user["stats"]["work_successes"] += 1
        user["stats"]["career_earnings"] += payout

        loot = self._roll_loot(career)
        for item_id in loot:
            self.bot.add_item(user, item_id, 1)

        loot_line = ", ".join(item.replace("_", " ").title() for item in loot) if loot else "No bonus loot this shift."
        next_job = self._next_career(user)
        promo_hint = ""
        if next_job and user["work_xp"] >= next_job["xp_required"]:
            promo_hint = f"\n{MochiEmojis.TROPHY} You can now try `/promote` toward **{next_job['name']}**."

        await ctx.send(
            embed=success_embed(
                f"{note}\n"
                f"{MochiEmojis.CURRENCY} Earned **{payout:,}** bits\n"
                f"{MochiEmojis.SKILL} Gained **{xp_gain} XP**\n"
                f"{MochiEmojis.BAG} Loot: **{loot_line}**{promo_hint}",
                title=f"Shift Complete: {career['name']}",
            )
        )

    @commands.hybrid_command(name="craft", description="Craft useful items from components.")
    @app_commands.describe(recipe="Try `golden_shield`.")
    async def craft(self, ctx, recipe: str):
        recipe = recipe.lower()
        user = self.bot.get_user(ctx.author.id)
        if recipe != "golden_shield":
            await ctx.send(embed=error_embed("Only `golden_shield` can be crafted right now."))
            return

        if user["inventory"].get("scrap_metal", 0) < 3:
            await ctx.send(embed=error_embed("You need **3 Scrap Metal** to craft a Golden Shield."))
            return

        self.bot.add_item(user, "scrap_metal", -3)
        self.bot.add_item(user, "golden_shield", 1)
        user["protection"]["shield_charges"] += 1
        await ctx.send(
            embed=success_embed(
                f"{MochiEmojis.SHIELD} Crafted **Golden Shield**. Your next robbery defense is stronger now.",
                title="Craft Complete",
            )
        )

    @commands.hybrid_command(name="collectincome", description="Claim passive business income.")
    async def collectincome(self, ctx):
        user = self.bot.get_user(ctx.author.id)
        payout = self.bot.apply_passive_income(user)
        if payout <= 0:
            await ctx.send(embed=error_embed("No passive income is ready yet. Check back after an hour."))
            return

        await ctx.send(
            embed=success_embed(
                f"{MochiEmojis.BUSINESS} Collected **{payout:,}** bits from your businesses.",
                title="Income Collected",
            )
        )

    @commands.hybrid_command(name="portfolio", description="View your businesses, stocks, and collectibles.")
    async def portfolio(self, ctx):
        user = self.bot.get_user(ctx.author.id)
        businesses = user.get("passive_income", {})
        stocks = user.get("stocks", {})
        collectibles = {
            item_id: amount
            for item_id, amount in user["inventory"].items()
            if item_id in COLLECTIBLES or item_id in {"padlock", "landmine", "fake_wallet"}
        }

        business_lines = []
        for business_id, owned in businesses.items():
            if owned["count"] > 0:
                business_lines.append(
                    f"{BUSINESSES[business_id]['name']}: x{owned['count']} ({owned['hourly_income'] * owned['count']:,}/hour)"
                )
        stock_lines = [f"{coin_id.title()}: {shares} shares" for coin_id, shares in stocks.items() if shares > 0]

        embed = info_embed("Your long-term empire at a glance.", title=f"{MochiEmojis.BUSINESS} Portfolio")
        embed.add_field(name="Businesses", value="\n".join(business_lines) or "None", inline=False)
        embed.add_field(name="Stocks", value="\n".join(stock_lines) or "None", inline=False)
        embed.add_field(name="Items", value=self._format_inventory(collectibles), inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="inventory", aliases=["inv"], description="View your bits, crates, items, and holdings.")
    async def inventory(self, ctx):
        user = self.bot.get_user(ctx.author.id)
        passive_ready = self.bot.apply_passive_income(user)
        bank_interest = self.bot.apply_bank_interest(user)

        item_entries = []
        utility_entries = []
        crate_entries = []
        collectible_entries = []

        for item_id, amount in user.get("inventory", {}).items():
            if amount <= 0:
                continue
            if item_id in COLLECTIBLES:
                collectible_entries.append((COLLECTIBLES[item_id]["name"], amount))
                continue

            item_info = SHOP_ITEMS.get(item_id)
            if item_info is None:
                item_entries.append((item_id.replace("_", " ").title(), amount))
                continue

            if item_info["type"] == "crate":
                crate_entries.append((item_info["name"], amount))
            elif item_info["type"] == "utility":
                utility_entries.append((item_info["name"], amount))
            else:
                item_entries.append((item_info["name"], amount))

        business_entries = []
        for business_id, owned in user.get("passive_income", {}).items():
            count = owned.get("count", 0)
            if count > 0:
                business_entries.append((f"{BUSINESSES[business_id]['name']} ({owned['hourly_income'] * count:,}/hour)", count))

        skill_entries = [(SKILLS[skill_id]["name"], 1) for skill_id in user.get("skills", []) if skill_id in SKILLS]
        protection = user.get("protection", {})
        protection_lines = [
            f"Golden shield charges: **{protection.get('shield_charges', 0)}**",
            f"Fake wallet: **{'On' if protection.get('fake_wallet') else 'Off'}**",
        ]

        embed = discord.Embed(
            title=f"{MochiEmojis.BAG} {ctx.author.display_name}'s Inventory",
            color=MochiColor.PINK,
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(
            name="Balances",
            value=(
                f"{MochiEmojis.CURRENCY} Wallet: **{user['wallet']:,}** bits\n"
                f"{MochiEmojis.BANK} Bank: **{user['bank']:,}** bits\n"
                f"{MochiEmojis.BUSINESS} Collected now: **{passive_ready:,}**\n"
                f"{MochiEmojis.TAX} Interest now: **{bank_interest:,}**"
            ),
            inline=False,
        )
        embed.add_field(name=f"{MochiEmojis.CRATE} Crates", value=self._format_named_counts(crate_entries), inline=True)
        embed.add_field(name=f"{MochiEmojis.BAG} Items", value=self._format_named_counts(item_entries), inline=True)
        embed.add_field(name=f"{MochiEmojis.SHIELD} Utilities", value=self._format_named_counts(utility_entries), inline=True)
        embed.add_field(name="Collectibles", value=self._format_named_counts(collectible_entries), inline=False)
        embed.add_field(name=f"{MochiEmojis.BUSINESS} Businesses", value=self._format_named_counts(business_entries), inline=False)
        embed.add_field(name=f"{MochiEmojis.MARKET} Stocks", value=self._format_stocks(user.get("stocks", {})), inline=False)
        embed.add_field(name=f"{MochiEmojis.SKILL} Skills", value=self._format_named_counts(skill_entries), inline=False)
        embed.add_field(name="Protection", value="\n".join(protection_lines), inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", description="Show economy leaderboards.")
    @app_commands.describe(category="Try richest, robbers, or workers.")
    async def leaderboard(self, ctx, category: str = "richest"):
        category = category.lower()
        entries = []
        for user_id, user in self.bot.db.items():
            if category == "robbers":
                value = user["stats"]["rob_successes"]
            elif category == "workers":
                value = user["stats"]["work_successes"]
            else:
                value = user["wallet"] + user["bank"]
                category = "richest"
            entries.append((user_id, value))

        entries.sort(key=lambda entry: entry[1], reverse=True)
        top = entries[:10]
        embed = info_embed("", title=f"{MochiEmojis.TROPHY} {category.title()} Leaderboard", color=MochiColor.GOLD)
        for rank, (user_id, value) in enumerate(top, start=1):
            member = ctx.guild.get_member(user_id) if ctx.guild else None
            name = member.display_name if member else str(user_id)
            suffix = "bits" if category == "richest" else "wins"
            embed.add_field(name=f"#{rank} {name}", value=f"**{value:,}** {suffix}", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="bounty", description="Place a robbery bounty on a member.")
    @app_commands.describe(member="The target.", amount="The reward for the next successful robber.")
    async def bounty(self, ctx, member: discord.Member, amount: int):
        if amount <= 0 or member.id == ctx.author.id:
            await ctx.send(embed=error_embed("Choose a positive amount and a target that is not yourself."))
            return

        user = self.bot.get_user(ctx.author.id)
        if user["wallet"] < amount:
            await ctx.send(embed=error_embed("You do not have enough bits to fund that bounty."))
            return

        user["wallet"] -= amount
        bounties = self.bot.server_state["bounties"]
        bounties[member.id] = bounties.get(member.id, 0) + amount
        await ctx.send(
            embed=success_embed(
                f"{MochiEmojis.ROB} A bounty of **{bounties[member.id]:,}** bits is now on {member.mention}.",
                title="Bounty Placed",
            )
        )

    @commands.hybrid_command(name="market", description="View the fake bot market.")
    async def market(self, ctx):
        self._ensure_market()
        market = self.bot.server_state["market"]
        embed = info_embed(
            "Prices shift every 30 minutes. Buy low, sell high, or regret everything.",
            title=f"{MochiEmojis.MARKET} Bot Market",
            color=MochiColor.GOLD,
        )
        for coin_id, coin in market["coins"].items():
            embed.add_field(name=coin["name"], value=f"`{coin_id}` • {coin['price']:,} bits/share", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="buystock", description="Buy shares from the fake bot market.")
    @app_commands.describe(coin_id="Which coin to buy.", quantity="How many shares.")
    async def buystock(self, ctx, coin_id: str, quantity: int):
        self._ensure_market()
        coin_id = coin_id.lower()
        if quantity <= 0:
            await ctx.send(embed=error_embed("Quantity must be at least 1."))
            return

        market = self.bot.server_state["market"]
        if coin_id not in market["coins"]:
            await ctx.send(embed=error_embed("That market listing does not exist."))
            return

        user = self.bot.get_user(ctx.author.id)
        price = market["coins"][coin_id]["price"]
        total_cost = price * quantity
        if user["wallet"] < total_cost:
            await ctx.send(embed=error_embed("You do not have enough wallet bits for that trade."))
            return

        user["wallet"] -= total_cost
        user["stocks"][coin_id] = user["stocks"].get(coin_id, 0) + quantity
        await ctx.send(
            embed=success_embed(
                f"Bought **{quantity}** shares of **{market['coins'][coin_id]['name']}** for **{total_cost:,}** bits.",
                title="Stock Purchased",
            )
        )

    @commands.hybrid_command(name="sellstock", description="Sell shares from the fake bot market.")
    @app_commands.describe(coin_id="Which coin to sell.", quantity="How many shares.")
    async def sellstock(self, ctx, coin_id: str, quantity: int):
        self._ensure_market()
        coin_id = coin_id.lower()
        if quantity <= 0:
            await ctx.send(embed=error_embed("Quantity must be at least 1."))
            return

        user = self.bot.get_user(ctx.author.id)
        if user["stocks"].get(coin_id, 0) < quantity:
            await ctx.send(embed=error_embed("You do not own that many shares."))
            return

        market = self.bot.server_state["market"]
        if coin_id not in market["coins"]:
            await ctx.send(embed=error_embed("That market listing does not exist."))
            return

        proceeds = market["coins"][coin_id]["price"] * quantity
        user["stocks"][coin_id] -= quantity
        if user["stocks"][coin_id] <= 0:
            user["stocks"].pop(coin_id, None)
        user["wallet"] += proceeds
        await ctx.send(
            embed=success_embed(
                f"Sold **{quantity}** shares of **{market['coins'][coin_id]['name']}** for **{proceeds:,}** bits.",
                title="Stock Sold",
            )
        )

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
