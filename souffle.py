import asyncio

import discord
from discord.ext import commands
import pickle
import time
import aiohttp

dev_guild = discord.Object(id=565434676877983772)


class Souffle(commands.Bot):
    def __init__(self, prefix: str, status: discord.Status, intents: discord.Intents) -> None:
        super().__init__(prefix, status=status, intents=intents)
        self.uptime = time.time()
        self.cmd_count = 0
        self.aiohttp_session = None
        self.remove_command("help")
        with open('guilds.pickle', 'rb') as f:
            self.verified_guilds = pickle.load(f)

    async def on_ready(self) -> None:
        """準備完了"""
        print(f"Logged in to [{self.user}]")
        self.aiohttp_session = aiohttp.ClientSession(loop=self.loop)
        await self.load_extension("music")
        await self.load_extension("developer")
        await asyncio.sleep(3)
        await self.tree.sync()
        await self.tree.sync(guild=dev_guild)

