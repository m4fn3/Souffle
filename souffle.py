import aiohttp
import discord
from discord.ext import commands
import pickle
import time

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

    async def on_guild_join(self, guild: discord.Guild):
        guild = self.get_guild(781897166675116042)
        channel: discord.TextChannel
        if (channel := guild.system_channel) is None:
            channel = guild.text_channels[0]
        embed = discord.Embed(color=discord.Color.blue())
        embed.description = f"👋 招待ありがとうございます!\n" \
                            "──────────────\n" \
                            f"[/](https://discord.com/channels/{guild.id}/{channel.id}) と入力して利用可能なコマンドを確認できます\n" \
                            "※ 何も表示されない場合は下のボタンを押して権限を追加してください\n" \
                            "──────────────\n" \
                            f"[/player](https://discord.com/channels/{guild.id}/{channel.id}) ... 音楽操作パネルを表示"
        embed.set_footer(text="一部コマンドはDiscordの破壊的変更の影響で現在使用できません。今後の更新をお待ちください。")
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="権限を追加", url="https://discord.com/api/oauth2/authorize?client_id=742952261176655882&permissions=8&scope=bot%20applications.commands"))
        view.add_item(discord.ui.Button(label="公式サーバー", url="https://discord.gg/S3kujur2pA"))
        await channel.send(embed=embed, view=view)



