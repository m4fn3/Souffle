import aiohttp
import discord
from discord.ext import commands
import pickle
import time

import response

dev_guild = discord.Object(id=565434676877983772)


class Souffle(commands.Bot):
    def __init__(self, prefix: str, status: discord.Status, intents: discord.Intents) -> None:
        super().__init__(prefix, status=status, intents=intents)
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

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """サーバー参加時"""
        embed = discord.Embed(title=f"{guild.name} に参加しました。", color=0x00ffff)
        embed.description = f"サーバーID: {guild.id}\nメンバー数: {len(guild.members)}\nサーバー管理者: {str(guild.owner)} ({guild.owner.id})"
        await self.get_channel(744466739542360064).send(embed=embed)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        """サーバー退出時"""
        embed = discord.Embed(title=f"{guild.name} を退出しました。", color=0xff1493)
        embed.description = f"サーバーID: {guild.id}\nメンバー数: {len(guild.members)}\nサーバー管理者: {str(guild.owner)} ({guild.owner.id})"
        await self.get_channel(744466739542360064).send(embed=embed)
        if guild.id in self.verified_guilds:
            self.verified_guilds.discard(guild.id)
            channel = self.get_channel(888017049589260298)
            await channel.send(embed=response.success(f"{guild.name}({guild.id})を退出したので自動的に承認を取り下げました."))
            with open('guilds.pickle', 'wb') as f:
                pickle.dump(self.verified_guilds, f)
