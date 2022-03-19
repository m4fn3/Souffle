""" nextcord==2.0.0a3 (v9使用) - メッセージ読み取り可 """

import logging
import os
from dotenv import load_dotenv

import nextcord as discord
from emoji import Emoji
import response

load_dotenv(verbose=True)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TOKEN = os.getenv("TOKEN")
PREFIX = "."

logging.basicConfig(level=logging.INFO)

emoji = Emoji()

if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)


    @client.event
    async def on_ready():
        print(f"Logged in to [{client.user}]")

    @client.event
    async def on_message(message: discord.Message) -> None:
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
                                        f"[/player](https://discord.com/channels/{message.guild.id}/{message.channel.id}) と入力して音楽操作パネルを表示してみてください！\n" \
                                        f"※ 何も表示されない場合は下のボタンを押して権限を追加してください"
                    embed.set_image(url="https://media.discordapp.net/attachments/843462170696351754/954200194591899698/IMG_3322.jpg")
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="権限を追加", url="https://discord.com/api/oauth2/authorize?client_id=742952261176655882&permissions=8&scope=bot%20applications.commands"))
                    view.add_item(discord.ui.Button(label="公式サーバー", url="https://discord.gg/S3kujur2pA"))
                    await message.reply(embed=embed, view=view)
                elif message.guild.get_member(887274006993047562) is None:
                    embed = response.error("Due to the impact of Discord's breaking changes, this feature has been moved to sub-BOT. Please click the button below to invite.")
                    embed.set_footer(text="Discordの破壊的変更の影響によりこの機能はサブBOTに移行されました。下のボタンから追加できます。")
                    view = discord.ui.View()
                    view.add_item(discord.ui.Button(label="追加/Invite", url="https://discord.com/oauth2/authorize?client_id=887274006993047562&scope=bot+applications.commands&permissions=8"))
                    view.add_item(discord.ui.Button(label="公式Server", url="https://discord.gg/S3kujur2pA"))
                    await message.reply(embed=embed, view=view)


    client.run(TOKEN)
