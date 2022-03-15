import discord


def error(text: str, title: str = None):
    embed = discord.Embed(
        description=f"<:xx:953186398075252747> {text}",
        color=discord.Color.red()
    )
    if title:
        embed.title = title
    return embed


def success(text: str, title: str = None):
    embed = discord.Embed(
        description=f"<:oo:953186398461108234> {text}",
        color=discord.Color.green()
    )
    if title:
        embed.title = title
    return embed


def warning(text: str, title: str = None):
    embed = discord.Embed(
        description=f"<:warn:953186235034251274> {text}",
        color=0xf7b51c
    )
    if title:
        embed.title = title
    return embed


def normal(text: str, title: str = None):
    embed = discord.Embed(
        description=f"{text}",
        color=discord.Color.blue()
    )
    if title:
        embed.title = title
    return embed
