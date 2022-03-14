from discord.ext import commands


class Souffle(commands.Bot):
    def __init__(self, prefix, status, intents) -> None:
        super().__init__(prefix, status=status, intents=intents)

    async def on_ready(self) -> None:
        print(f"Logged in to [{self.user}]")
        await self.load_extension("music")
        await self.tree.sync()
