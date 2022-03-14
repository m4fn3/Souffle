import discord


def error(text: str, title: str = None):
    embed = discord.Embed(
        description=f"<:xx:773568207222210650> {text}",
        color=discord.Color.red()
    )
    if title:
        embed.title = title
    return embed


def success(text: str, title: str = None):
    embed = discord.Embed(
        description=f"<:oo:773568207231123476> {text}",
        color=discord.Color.green()
    )
    if title:
        embed.title = title
    return embed


def warning(text: str, title: str = None):
    embed = discord.Embed(
        description=f"<:warn:773569061442289674> {text}",
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
