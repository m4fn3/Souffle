import discord
from discord.ext import commands
import pickle
import time

import response
from emoji import Emoji

emoji = Emoji()
dev_guild = discord.Object(id=565434676877983772)


class Souffle(commands.Bot):
    def __init__(self, prefix: str, status: discord.Status, intents: discord.Intents) -> None:
        super().__init__(prefix, status=status, intents=intents)
        self.uptime = time.time()
        with open('guilds.pickle', 'rb') as f:
            self.verified_guilds = pickle.load(f)

    async def on_ready(self) -> None:
        """準備完了"""
        print(f"Logged in to [{self.user}]")
        await self.load_extension("music")
        await self.load_extension("developer")
        await self.tree.sync()
        await self.tree.sync(guild=dev_guild)
        # for e in self.get_guild(953185304267862066).emojis:
        #     print(f"{e.name} = \"<:{e.name}:{e.id}>\"")

    async def on_message(self, message: discord.Message) -> None:
        """メッセージ受信時"""
        cmd = ('notice', 'join', 'j', 'follow', 'loop_queue', 'lq', 'loopqueue', 'resume', 're', 'rs', 'res', 'accept', 'ac', 'ads', 'refuse', 'rf', 'reload', 'rl', 'menu', 'm', 'queue', 'q',
               'restart', 'skip', 's', 'quit', 'pause', 'ps', 'stop', 'clear', 'cl', 'load', 'random', 'exe', 'now_playing', 'np', 'my', 'mylist', 'play', 'p', 'player', 'pl', 'db', 'language',
               'lang', 'process', 'pr', 'invite', 'inv', 'about', 'info', 'ping', 'pg', 'add', 'body', 'character', 'back', 'weapon', 'head', 'base', 'remove', 'rm', 'cmd', 'help', 'shuffle', 'save',
               'list', 'back', 'weapon', 'character', 'head', 'body', 'base', 'show', 'loop', 'l', 'disconnect', 'dc', 'dis', 'leave', 'lv', 'delete', 'del', 'set')
        cmd_music = ['player', 'pl', 'play', 'p', 'join', 'j', 'disconnect', 'dc', 'dis', 'leave', 'lv', 'queue', 'q', 'pause', 'ps', 'stop', 'resume', 're', 'rs', 'res', 'skip', 's', 'now_playing',
                     'np', 'remove', 'rm', 'clear', 'cl', 'shuffle', 'loop', 'l', 'loop_queue', 'lq', 'loopqueue']
        if message.content.startswith(("m!", ".")):
            if message.content.lstrip(".").lstrip("m!").startswith(cmd):
                # スラコマ移行のお知らせ
                c = message.content.lstrip(".").lstrip("m!").split()[0]
                if c in cmd_music:
                    embed = discord.Embed(color=0xf7b51c)
                    embed.description = f"{emoji.warn} __音楽再生機能はスラッシュコマンドに移行されました__\n" \
                                        f"`/player` と入力して音楽操作パネルを表示してみてください！\n" \
                                        f"※ 何も表示されない場合は下のボタンを押して権限を追加してください"
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="権限を追加", url="https://discord.com/api/oauth2/authorize?client_id=742952261176655882&permissions=8&scope=bot%20applications.commands"))
                    view.add_item(discord.ui.Button(label="公式サーバー", url="https://discord.gg/S3kujur2pA"))
                    await message.reply(embed=embed, view=view)
                else:
                    embed = response.error("This command is currently unavailable due to the effects of Discord's breaking changes. Please wait for future updates.\n")
                    embed.set_footer(text="Discordの破壊的変更の影響でこのコマンドは現在使用できません。今後の更新をお待ちください。")
                    await message.reply(embed=embed)
