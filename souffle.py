import aiohttp
import discord
from discord.ext import commands
import pickle
import time

import response

dev_guild = discord.Object(id=565434676877983772)


class Souffle(commands.Bot):
    def __init__(self, prefix: str, status: discord.Status, intents: discord.Intents) -> None:
        super().__init__(prefix, status=status, intents=intents, help_command=None)
        self.uptime = time.time()
        self.cmd_count = 0
        self.aiohttp_session = None
        with open('guilds.pickle', 'rb') as f:
            self.verified_guilds = pickle.load(f)

    async def on_ready(self) -> None:
        """準備完了"""
        print(f"Logged in to [{self.user}]")
        self.aiohttp_session = aiohttp.ClientSession(loop=self.loop)
        await self.load_extension("music")
        await self.load_extension("developer")
        await self.tree.sync()
        await self.tree.sync(guild=dev_guild)
        # for e in self.get_guild(953185304267862066).emojis:
        #     print(f"{e.name} = \"<:{e.name}:{e.id}>\"")

