import discord
from discord.ext import commands


class Souffle(commands.Bot):
    def __init__(self, prefix: str, status: discord.Status, intents: discord.Intents) -> None:
        super().__init__(prefix, status=status, intents=intents)

    async def on_ready(self) -> None:
        """準備完了"""
        print(f"Logged in to [{self.user}]")
        await self.load_extension("music")
        await self.tree.sync()
        # for e in self.get_guild(953185304267862066).emojis:
        #     print(f"{e.name} = \"<:{e.name}:{e.id}>\"")

