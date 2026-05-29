import discord


class MochiColor:
    PINK = 0xFFB7C5
    GREEN = 0xB2D3C2
    GOLD = 0xFFD700
    RED = 0xFF6B6B
    BLUE = 0x9ED8F5


class MochiEmojis:
    CURRENCY = "🪙"
    BANK = "🏦"
    BAG = "🎒"
    SUCCESS = "✅"
    ERROR = "❌"
    LOADING = "⏳"
    DAILY = "🍡"
    PROFILE = "🪪"
    SHOP = "🛍️"
    PAGE = "📖"
    TRADE = "🤝"
    SLOTS = "🎰"
    ROB = "🕵️"
    LOTTERY = "🎟️"
    TROPHY = "🏆"
    WORK = "🍵"
    GIFT = "🎁"
    ADMIN = "🛠️"
    SKILL = "🧠"
    BUSINESS = "🏢"
    CRATE = "📦"
    SHIELD = "🛡️"
    MARKET = "📈"
    MONEY_BAG = "💰"
    TAX = "🧾"
    HOSPITAL = "🏥"


def _base_embed(
    description: str,
    *,
    title: str | None = None,
    color: int,
) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)


def error_embed(description: str, *, title: str = "Something Went Wrong") -> discord.Embed:
    return _base_embed(description, title=title, color=MochiColor.RED)


def success_embed(description: str, *, title: str = "Success") -> discord.Embed:
    return _base_embed(description, title=title, color=MochiColor.GREEN)


def info_embed(
    description: str,
    *,
    title: str = "Mochi Bot",
    color: int = MochiColor.BLUE,
) -> discord.Embed:
    return _base_embed(description, title=title, color=color)
