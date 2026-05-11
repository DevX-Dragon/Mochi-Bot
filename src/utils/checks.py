from discord import app_commands
from discord.ext import commands


def is_admin_id(bot, user_id):
    return user_id in getattr(bot, "admins", [])


def admin_only():
    async def predicate(ctx):
        return is_admin_id(ctx.bot, ctx.author.id)

    return commands.check(predicate)


def app_admin_only():
    async def predicate(interaction):
        return is_admin_id(interaction.client, interaction.user.id)

    return app_commands.check(predicate)
