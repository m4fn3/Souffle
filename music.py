import pickle

import aiohttp
from bs4 import BeautifulSoup
import discord
from discord.ext import commands
from discord import app_commands

import asyncio
from async_timeout import timeout
import os
import random
import re
import traceback2
from typing import Union, Optional, List
import yt_dlp as youtube_dl

import response
from emoji import Emoji
import souffle

ytdl_options = {
    'add-header': 'Accept-Language:ja-JP',
    'format': 'bestaudio/best',
    'outtmpl': 'downloads/%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # ipv6 addresses cause issues sometimes
    'cookies': 'cookies.txt'
}

ffmpeg_options = {
    'before_options': '-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_options)
yt_params = {'key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8', 'alt': 'json'}

emoji = Emoji()


class YTDLSource(discord.PCMVolumeTransformer):
    """YouTubeデータ取得"""

    def __init__(self, source, *, data):
        """初期化処理"""
        super().__init__(source)
        self.data = data

        self.title = data["title"]
        self.url = data["webpage_url"]
        self.duration = data["duration"]

    def __getitem__(self, item):
        return self.data[item]

    @classmethod
    async def create_source(cls, search: str, *, loop, process=True):
        """動画データ取得"""
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=search, download=False, process=process))
        return data

    @classmethod
    async def stream(cls, data, *, loop):
        """動画ストリーム用データ取得"""
        loop = loop or asyncio.get_event_loop()

        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url=data["webpage_url"], download=False))
        return cls(
            discord.FFmpegPCMAudio(
                data['url'], **ffmpeg_options
            ), data=data
        )


async def get_related_video(session: aiohttp.ClientSession, video_id: str, duration: int, history: list) -> Union[str, None]:
    """関連動画をinnertubeで取得"""
    resp = await session.post(
        "https://youtubei.googleapis.com/youtubei/v1/next/", params=yt_params,
        json={'videoId': video_id, 'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20210223.09.00'}}}
    )
    data = await resp.json()
    items = data["contents"]["twoColumnWatchNextResults"]["secondaryResults"]["secondaryResults"]["results"]
    ids = [
        item["compactVideoRenderer"]["videoId"] for item in items
        if "compactVideoRenderer" in item and "videoId" in item["compactVideoRenderer"] and item["compactVideoRenderer"]["videoId"] not in history and
           "lengthText" in item["compactVideoRenderer"] and text_to_duration(item["compactVideoRenderer"]["lengthText"]["simpleText"]) <= duration * 4
    ]
    if len(ids) == 0:
        ids = [
            item["compactVideoRenderer"]["videoId"] for item in items
            if "compactVideoRenderer" in item and "videoId" in item["compactVideoRenderer"] and item["compactVideoRenderer"]["videoId"] not in history
        ]
        if len(ids) == 0:
            return None
    return ids[0]


class Player:
    """楽曲情報の保持/再生を行うプレイヤー"""

    def __init__(self, interaction):
        """初期化処理"""
        self.bot = interaction.client
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.volume = 1
        self.loop = 0  # 0: off / 1: loop / 2: loop_queue / 3: auto
        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        self.current = None
        self.menu = None
        self.history = []
        self.task = interaction.client.loop.create_task(
            self.player_loop()
        )

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0)', 'Accept-Encoding': 'gzip, deflate, br', 'Accept': '*/*', 'Connection': 'keep-alive',
            'X-YouTube-Client-Name': '1', 'X-YouTube-Client-Version': '2.20210223.09.00', 'Referer': 'https://www.youtube.com/'
        }
        self.session = aiohttp.ClientSession(headers=headers)

    async def player_loop(self):
        """音楽再生基盤"""
        try:
            while True:
                self.next.clear()
                try:
                    if len(self.queue._queue) == 0:
                        if self.menu is not None:
                            await self.menu.update()  # 予約曲が0でメニューがある場合
                        if self.guild.voice_client.channel.type == discord.ChannelType.stage_voice and self.guild.voice_client.channel.permissions_for(self.guild.me).manage_channels:
                            if self.guild.voice_client.channel.instance is not None:
                                await self.guild.voice_client.channel.instance.edit(topic="まだ曲が追加されていません")
                    async with timeout(300):
                        data = await self.queue.get()
                except asyncio.TimeoutError:  # 自動切断
                    await self.channel.send(embed=response.warning("一定時間、操作がなかったため接続を切りました。"))
                    return self.destroy(self.guild)
                try:
                    source = await YTDLSource.stream(data, loop=self.bot.loop)
                except asyncio.CancelledError:
                    return
                except:
                    await self.channel.send(embed=response.error(f"音楽の処理中にエラーが発生しました\n```py\n{traceback2.format_exc()}```"))
                    continue
                source.volume = self.volume
                self.current = source
                self.guild.voice_client.play(
                    source,
                    after=lambda _: self.bot.loop.call_soon_threadsafe(self.next.set)
                )
                if self.menu:  # 再生中の曲はソースから情報を取得するため再生処理の後に実行
                    await self.menu.update()
                if self.guild.voice_client.channel.type == discord.ChannelType.stage_voice and self.guild.voice_client.channel.permissions_for(self.guild.me).manage_channels:
                    if self.guild.voice_client.channel.instance is None:
                        await self.guild.voice_client.channel.create_instance(topic=source.title)
                    else:
                        await self.guild.voice_client.channel.instance.edit(topic=source.title)
                await self.next.wait()
            self.guild.voice_client.stop()
            self.current = None
            if self.loop == 1:
                self.queue._queue.appendleft(data)
            elif self.loop == 2:
                await self.queue.put(data)
            elif self.loop == 3 and len(self.queue._queue) == 0:
                self.history.append(data["id"])  # 履歴管理
                if len(self.history) > 5:  # max: 5
                    del self.history[1]
                video_id = await get_related_video(self.session, data["id"], data["duration"], self.history)
                if video_id is not None:
                    data = await YTDLSource.create_source("https://www.youtube.com/watch?v=" + video_id, loop=self.bot.loop)
                    await self.queue.put(data)

        except asyncio.exceptions.CancelledError:
            pass
        # except:  # エラーを報告
        #     await self.bot.get_channel(964431944484016148).send(f"```py\n{traceback2.format_exc()}\n```")


def destroy(self, guild: discord.Guild):
    """パネル破棄"""
    return self.bot.loop.create_task(guild.voice_client.disconnect(force=False))


class Request(discord.ui.Modal, title="楽曲追加"):
    """楽曲追加用モーダル"""
    text = discord.ui.TextInput(
        label='再生したい曲名またはURLを入力してください',
        style=discord.TextStyle.long,
        placeholder='例) シャルル\nhttps://youtu.be/TA5OFS_xX0c\n※ 改行することで複数曲同時に追加できます'
    )

    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.cog = interaction.client.get_cog("Music")

    async def on_submit(self, interaction: discord.Interaction):
        """音楽の追加処理"""
        msg = await self.cog.play(interaction, self.text.value)
        await self.cog.get_player(interaction).menu.update()
        await msg.delete(delay=3)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        """例外発生時"""
        await interaction.channel.send(embed=response.error(f"処理中に予期しないエラーが発生しました。\n```\n{traceback2.format_exc()}```"))


class RemoveSelect(discord.ui.Select):
    """曲削除用セレクトメニュー"""

    def __init__(self, interaction: discord.Interaction, songs: list):
        super().__init__(placeholder="削除したい曲を選択してください", min_values=1, max_values=len(songs), options=songs)
        self.interaction = interaction

    async def callback(self, interaction: discord.Interaction):
        """選択完了後"""
        await self.interaction.delete_original_message()  # 選択画面を削除(元のinteraction)
        self.view.stop()
        cog = interaction.client.get_cog("Music")
        player = cog.get_player(interaction)
        for i in sorted([int(i) for i in self.values], reverse=True):
            del player.queue._queue[i]
        await cog.get_player(interaction).menu.update()
        msg = await interaction.channel.send(embed=response.success(f"予約された曲から{len(self.values)}曲を削除しました"))
        await msg.delete(delay=3)


class RemoveView(discord.ui.View):
    """曲削除用UI"""

    def __init__(self, interaction: discord.Interaction, songs: list):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.add_item(RemoveSelect(interaction, songs))

    async def on_timeout(self):
        await self.interaction.delete_original_message()


class MenuView(discord.ui.View):
    """操作用ボタン"""

    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.cog = interaction.client.get_cog("Music")

    @discord.ui.button(emoji=emoji.repeat)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """繰り返し再生の設定"""
        player = self.cog.get_player(interaction)
        embed: discord.Embed
        if player.loop == 0:
            player.loop += 1
            button.emoji = emoji.repeat_one
            button.style = discord.ButtonStyle.blurple
            embed = response.success("現在再生中の曲の繰り返しを有効にしました")
        elif player.loop == 1:
            player.loop += 1
            button.emoji = emoji.repeat
            button.style = discord.ButtonStyle.green
            embed = response.success("予約された曲全体の曲の繰り返しを有効にしました")
        elif player.loop == 2:
            player.loop += 1
            button.emoji = emoji.auto
            button.style = discord.ButtonStyle.red
            embed = response.success("曲の自動再生を有効にしました")
        else:  # 3
            player.loop = 0
            button.emoji = emoji.repeat
            button.style = discord.ButtonStyle.grey
            embed = response.success("曲の繰り返しを無効にしました")
        msg = await interaction.channel.send(embed=embed)
        await self.update(msg)
        await interaction.response.defer()

    @discord.ui.button(emoji=emoji.shuffle)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """予約済曲のシャッフル"""
        msg = await self.cog.shuffle(interaction)
        await self.update(msg)
        await interaction.response.defer()

    @discord.ui.button(emoji=emoji.pause, style=discord.ButtonStyle.blurple)
    async def play(self, interaction: discord.Interaction, button: discord.ui.Button):
        """再生/停止 切り替え"""
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = self.interaction.guild.voice_client
        embed: discord.Embed
        if not voice_client or not voice_client.is_connected():  # 未接続
            embed = response.error("現在再生中の音楽はありません")
        elif voice_client.is_playing():
            button.emoji = emoji.play
            button.style = discord.ButtonStyle.green
            voice_client.pause()
            embed = response.success("音楽の再生を一時停止しました")
        elif voice_client.is_paused():
            button.emoji = emoji.pause
            button.style = discord.ButtonStyle.blurple
            voice_client.resume()
            embed = response.success("音楽の再生を再開しました")
        else:
            embed = response.error("現在再生中の音楽はありません")
        msg = await self.interaction.channel.send(embed=embed)
        await self.update(msg)
        await interaction.response.defer()

    @discord.ui.button(emoji=emoji.skip)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """曲のスキップ"""
        msg = await self.cog.skip(interaction)
        player = self.cog.get_player(interaction)
        if player.loop != 3:
            await self.update(msg)
        await interaction.response.defer()

    @discord.ui.button(emoji=emoji.question)
    async def help(self, interaction: discord.Interaction, button: discord.ui.Button):
        """予約済み曲のクリア"""
        embed = discord.Embed(color=discord.Color.blue())
        embed.description = f"{emoji.repeat} ... 曲のループ設定です(押すごとに 1曲繰り返し/全曲繰り返し/自動再生/オフ と切り替わります)\n" \
                            f"{emoji.shuffle} .. .曲をシャッフルします\n" \
                            f"{emoji.pause} ... 音楽の再生を停止/再開します\n" \
                            f"{emoji.skip} ... 再生中の曲をスキップします\n" \
                            f"{emoji.question} ... 使い方を表示します\n" \
                            f"{emoji.add} ... 音楽を追加します\n" \
                            f"{emoji.back} ... 前のページの曲を表示します\n" \
                            f"{emoji.next} ... 次のページの曲を表示します\n" \
                            f"{emoji.remove} ... 音楽を削除します(表示されているページの曲のみ選択できます)\n" \
                            f"{emoji.disconnect} ... 再生を停止して切断します"
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(emoji=emoji.add)
    async def request(self, interaction: discord.Interaction, button: discord.ui.Button):
        """楽曲追加"""
        await interaction.response.send_modal(Request(interaction))

    @discord.ui.button(emoji=emoji.back)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.cog.get_player(interaction)
        page = len(player.queue._queue) // 10 + 1
        if 1 < player.menu.page:
            page = player.menu.page - 1
        await player.menu.update(self, page=page)
        await interaction.response.defer()

    @discord.ui.button(emoji=emoji.next)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        player = self.cog.get_player(interaction)
        page = 1
        if player.menu.page < len(player.queue._queue) // 10 + 1:
            page = player.menu.page + 1
        await player.menu.update(self, page=page)
        await interaction.response.defer()

    @discord.ui.button(emoji=emoji.remove)
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        """楽曲の削除"""
        player = self.cog.get_player(interaction)
        if len(player.queue._queue) == 0:
            msg = await interaction.channel.send(embed=response.error("現在予約されている曲はありません"))
            await interaction.response.defer()
            return await self.update(msg)
        songs = [discord.SelectOption(label=d["title"], value=str(i)) for i, d in enumerate(player.queue._queue) if
                 10 * (player.menu.page - 1) <= i < min(len(player.queue._queue), 10 * player.menu.page)]
        view = RemoveView(interaction, songs)
        await interaction.response.send_message(embed=response.normal(f"削除したい曲を選んでください ({player.menu.page} / {len(player.queue._queue) // 10 + 1} ページ)"), view=view)

    @discord.ui.button(emoji=emoji.disconnect, style=discord.ButtonStyle.red)
    async def disconnect(self, interaction: discord.Interaction, button: discord.ui.Button):
        """VCからの切断"""
        await self.cog.disconnect(interaction)

    async def update(self, msg: discord.Message):  # 各アクション実行後に画面更新&メッセージ削除
        """最新状態への画面更新"""
        await self.cog.get_player(self.interaction).menu.update(self)
        await msg.delete(delay=3)


class Menu:
    """音楽操作パネル"""

    def __init__(self, interaction: discord.Interaction):
        """初期化処理"""
        self.interaction = interaction
        self.bot = interaction.client
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.page = 1
        self.msg = None
        self.view = None

    async def initialize(self):
        """初期化処理(非同期)"""
        self.view = MenuView(self.interaction)
        if self.guild.voice_client.is_paused():
            self.view.play.emoji = emoji.play
            self.view.play.style = discord.ButtonStyle.green
        player = self.bot.get_cog("Music").get_player(self.interaction)
        if player.loop == 1:
            self.view.loop.emoji = emoji.repeat_one
            self.view.loop.style = discord.ButtonStyle.blurple
        elif player.loop == 2:
            self.view.loop.emoji = emoji.repeat
            self.view.loop.style = discord.ButtonStyle.green
        elif player.loop == 3:
            self.view.loop.emoji = emoji.auto
            self.view.loop.style = discord.ButtonStyle.red
        self.msg = await self.channel.send(embed=response.normal("読込中..."), view=self.view)
        await self.update()

    async def update(self, view: discord.ui.View = None, page: int = 1):
        """最新状態への画面更新"""
        player = self.bot.get_cog("Music").get_player(self.interaction)
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = self.interaction.guild.voice_client
        self.page = page
        text = ""
        if voice_client.source is not None:
            text += f"▷[{voice_client.source.title}]({voice_client.source.url}) | {duration_to_text(voice_client.source.duration)}\n"
            text += "──────────────"
        elif player.queue.empty():
            text += f"まだ曲が追加されていません\n──────────────\n{emoji.add}を押して曲を追加しましょう!\n詳しくは{emoji.question}を押して確認してください"

        for i in range(10 * (page - 1), min(len(player.queue._queue), 10 * page)):  # 最大10曲
            d = player.queue._queue[i]
            text += f"\n{i + 1}. [{d['title']}]({d['webpage_url']}) | {duration_to_text(d['duration'])}"

        if player.loop == 3 and voice_client.source is not None:
            text += f"\n⇒ [関連曲の自動再生](https://discord.com/channels/{self.guild.id}/{self.channel.id})"

        embed = discord.Embed(description=text, color=discord.Color.blurple())
        footer = f"\n\n現在{len(player.queue._queue)}曲が予約されています ({page} / {len(player.queue._queue) // 10 + 1} ページ)"
        embed.set_footer(text=footer)

        if view is None:
            await self.msg.edit(content=None, embed=embed)
        else:
            await self.msg.edit(content=None, embed=embed, view=view)

    async def destroy(self):
        """操作パネルの破棄"""
        self.view.stop()
        self.view.clear_items()
        await self.msg.delete()


def duration_to_text(seconds: int) -> str:
    """秒からの変換"""
    if seconds == 0:
        return "LIVE"
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if hour > 0:
        return "%d:%02d:%02d" % (hour, minutes, seconds)
    else:
        return "%02d:%02d" % (minutes, seconds)


def text_to_duration(length: str) -> int:
    """秒への変換"""
    l = length.split(":")
    duration = 0
    for idx, t in enumerate(l):
        duration += (60 ** (len(l) - idx - 1)) * int(t)
    return duration


@app_commands.context_menu(name="検索して音楽を追加")
async def play_context_menu(interaction: discord.Interaction, message: discord.Message):
    cog = interaction.client.get_cog("Music")
    guild_id: int
    if interaction.guild.id in cog.players:
        guild_id = interaction.guild.id
    else:
        voice_client = discord.utils.find(lambda v: message.author.id in [u.id for u in v.channel.members], interaction.client.voice_clients)
        if voice_client is None or voice_client.guild.id not in cog.players:
            return await interaction.response.send_message(embed=response.error("先にボイスチャンネルに接続してください!"))
        guild_id = voice_client.guild.id
    msg = await cog.play(interaction, message.content, guild_id)
    await cog.players[guild_id].menu.update()
    await msg.delete(delay=3)


class Music(commands.Cog):
    """コマンド定義"""

    def __init__(self, bot: souffle.Souffle):
        """初期化処理"""
        self.bot = bot
        self.players = {}
        self.wait_leave = {}

        self.bot.tree.add_command(play_context_menu)

    def get_player(self, interaction: discord.Interaction):
        """プレイヤーの取得"""
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            player = Player(interaction)
            self.players[interaction.guild.id] = player
        return player

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
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
        embed.set_footer(text="音楽再生以外の装飾等の機能はDiscordの破壊的変更の影響によりMilkCaféに移行されました。必要な場合は下のボタンから別途追加してください。\n"
                              "Due to the impact of Discord's breaking changes, feature like costume has been moved to MilkCafé. Please click the button below to invite.")
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="権限を追加",
            url=f"https://discord.com/api/oauth2/authorize?client_id=742952261176655882&permissions=8&scope=bot%20applications.commands&guild_id={guild.id}")
        )
        view.add_item(discord.ui.Button(
            label="MilkCaféを追加",
            url=f"https://discord.com/oauth2/authorize?client_id=887274006993047562&scope=bot+applications.commands&permissions=8&guild_id={guild.id}")
        )
        view.add_item(discord.ui.Button(label="公式Server", url="https://discord.gg/S3kujur2pA"))
        await channel.send(embed=embed, view=view)

        embed = discord.Embed(title=f"{guild.name} に参加しました。", color=0x00ffff)
        embed.description = f"サーバーID: {guild.id}\nメンバー数: {len(guild.members)}\nサーバー管理者: {str(guild.owner)} ({guild.owner.id})"
        await self.bot.get_channel(744466739542360064).send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        embed = discord.Embed(title=f"{guild.name} を退出しました。", color=0xff1493)
        embed.description = f"サーバーID: {guild.id}\nメンバー数: {len(guild.members)}\nサーバー管理者: {str(guild.owner)} ({guild.owner.id})"
        await self.bot.get_channel(744466739542360064).send(embed=embed)
        if guild.id in self.bot.verified_guilds:
            self.bot.verified_guilds.discard(guild.id)
            channel = self.bot.get_channel(888017049589260298)
            await channel.send(embed=response.success(f"{guild.name}({guild.id})を退出したので自動的に承認を取り下げました."))
            with open('guilds.pickle', 'wb') as f:
                pickle.dump(self.bot.verified_guilds, f)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """音声系状態の変更を検出"""
        if before.channel is not None and after.channel is None:  # 退出
            bot_member = member.guild.get_member(self.bot.user.id)
            if member == bot_member:  # botの退出
                if member.guild.voice_client is not None and (member.guild.voice_client._potentially_reconnecting or member.guild.voice_client._handshaking):
                    pass  # 一時的な再接続の場合はデータを保持する
                else:
                    try:
                        self.players[member.guild.id].task.cancel()
                        await self.players[member.guild.id].session.close()
                        if self.players[member.guild.id].menu is not None:
                            self.bot.loop.create_task(self.players[member.guild.id].menu.destroy())
                        del self.players[member.guild.id]
                    except:
                        pass
            # 自動切断
            elif bot_member in before.channel.members:  # BOT接続しているVC
                voice_members = before.channel.members
                real_members = discord.utils.get(voice_members, bot=False)
                if len(voice_members) == 1 or real_members is None:
                    flag = asyncio.Event()
                    self.wait_leave[before.channel.id] = flag
                    try:
                        async with timeout(180):
                            await flag.wait()
                    except asyncio.TimeoutError:
                        if member.guild.voice_client.channel.type == discord.ChannelType.stage_voice and member.guild.voice_client.channel.permissions_for(member.guild.me).manage_channels:
                            if member.guild.voice_client.channel.instance is not None:
                                await member.guild.voice_client.channel.instance.delete()
                        await member.guild.voice_client.disconnect()
                    finally:
                        del self.wait_leave[before.channel.id]
        elif before.channel is None and after.channel is not None:  # 入室
            if after.channel.id in self.wait_leave:  # 切断保留中に入室した場合解除
                flag = self.wait_leave[after.channel.id]
                flag.set()

    async def log(self, interaction: discord.Interaction, name: str):
        self.bot.cmd_count += 1
        embed = discord.Embed(
            description=f"/{name} | {str(interaction.user)} | {interaction.channel.name} | {interaction.guild.name}({interaction.guild.id})",
            color=discord.Color.dark_theme()
        )
        content = {"embeds": [embed.to_dict()]}
        headers = {'Content-Type': 'application/json'}
        await self.bot.aiohttp_session.post(os.getenv("LOG_WH"), json=content, headers=headers)

    @app_commands.command(name="player", description="音楽再生操作パネルを起動します")
    @app_commands.choices(loop=[
        app_commands.Choice(name="一曲繰り返し", value=1),
        app_commands.Choice(name="全曲繰り返し", value=2),
        app_commands.Choice(name="自動再生", value=3),
    ])
    async def player_(self, interaction: discord.Interaction, loop: Optional[app_commands.Choice[int]]):
        """操作パネルの起動"""
        await self.log(interaction, "player")
        # VCに接続していることを確認
        # if interaction.guild.voice_client is None: # interaction消費のため既に接続している旨のメッセージを送信
        if await self.join(interaction):
            return
        player = self.get_player(interaction)
        if player.menu is not None:  # 前のメニューを破棄
            old_menu = player.menu  # destroy()してからmenuがNoneになるまでの間にplayer_loopがメッセージを編集しようとするのを防ぐ
            player.menu = None  # 先にNone化
            await old_menu.destroy()
        if loop is not None:
            player.loop = loop.value
        menu = Menu(interaction)
        await menu.initialize()  # 初期化完了後にメニュー登録
        player.menu = menu

    @app_commands.command(name="search", description="音楽を検索します(自動的に候補が表示されます)")
    async def search(self, interaction: discord.Interaction, query: str):
        if interaction.guild.id not in self.players:
            return await interaction.response.send_message(embed=response.error("BOTはまだボイスチャンネルに接続していません"))
        await interaction.response.defer()
        embed = await self.process(interaction, query, False)
        await self.get_player(interaction).menu.update()
        msg = await interaction.followup.send(embed=embed)
        await msg.delete(delay=3)

    @search.autocomplete("query")
    async def query_autocomplete(self, interaction: discord.Interaction, query: str) -> List[app_commands.Choice[str]]:
        if interaction.guild.id not in self.players:
            return []
        player = self.get_player(interaction)
        if query == "":
            return []
        resp = await player.session.post(
            "https://youtubei.googleapis.com/youtubei/v1/search/", params=yt_params,
            json={'query': query, 'context': {'client': {'clientName': 'WEB', 'clientVersion': '2.20210223.09.00'}}}
        )
        data = await resp.json()
        results = data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"]
        return [app_commands.Choice(name=res["videoRenderer"]["title"]["runs"][0]["text"], value=res["videoRenderer"]["videoId"]) for res in results if "videoRenderer" in res]
        # ### 入力補完ver. ###
        # resp = await player.session.get(f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={query}")
        # data = await resp.json(content_type=None)  # 既定の text/javascript を無視してデコード
        # return [app_commands.Choice(name=name, value=name) for name in data[1]]

    @app_commands.command(name="lyrics", description="歌詞を表示します(正確な曲名の入力が必要)")
    async def lyrics(self, interaction: discord.Interaction, title: str):
        await self.log(interaction, f"lyrics {title}")
        headers = {'User-Agent': 'python-requests/2.26.0', 'Accept-Encoding': 'gzip, deflate, br', 'Accept': '*/*', 'Connection': 'keep-alive'}
        resp = await self.bot.aiohttp_session.get(f"https://www.google.com/search?q={title}+lyrics", headers=headers)
        page = await resp.text()
        soup = BeautifulSoup(page, "html.parser")
        try:
            lyrics = soup.find_all("div", class_="BNeawe tAd8D AP7Wnd")[-1].text
            meta = soup.find("div", class_="kCrYT").text
        except:
            await interaction.response.send_message(embed=response.error("歌詞が見つかりませんでした。曲名が正確に入力されているか確認してください。"))
        else:
            await interaction.response.send_message(embed=response.normal(text=lyrics, title=meta))

    @app_commands.command(name="invite", description="各種招待リンクを表示します")
    async def invite(self, interaction: discord.Interaction):
        await self.log(interaction, "invite")
        embed = discord.Embed(title="MilkCoffee", color=discord.Color.blue())
        embed.description = "音楽以外の諸機能は仕様変更の影響によりMilkCafeに移行されました。\n" \
                            "Due to the impact of Discord's breaking changes, feature like costume has been moved to MilkCafe"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="MilkCoffee",
            url=f"https://discord.com/api/oauth2/authorize?client_id=742952261176655882&permissions=8&scope=bot%20applications.commands")
        )
        view.add_item(discord.ui.Button(
            label="MilkCafe",
            url=f"https://discord.com/oauth2/authorize?client_id=887274006993047562&scope=bot+applications.commands&permissions=8")
        )
        view.add_item(discord.ui.Button(label="公式Server", url="https://discord.gg/S3kujur2pA"))
        await interaction.response.send_message(embed=embed, view=view)

    async def join(self, interaction: discord.Interaction):
        """VCに接続"""
        if interaction.guild.id not in self.bot.verified_guilds:
            embed = discord.Embed(
                description=f"負荷対策のため音楽機能はサーバーごとの承認制になっています。\n上に書いてある番号とミルクチョコ内のロビー画面のスクショ\nを[公式サーバー](https://discord.gg/h2ZNX9mSSN)の<#887981017539944498>に送ってください。",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(f"{interaction.guild.id}\nhttps://discord.gg/h2ZNX9mSSN", embed=embed)
            return True
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = interaction.guild.voice_client
        if interaction.user.voice is None:
            await interaction.response.send_message(embed=response.error("先にボイスチャンネルに接続してください!"), ephemeral=True)
            return True
        elif voice_client is None or not voice_client.is_connected():
            if voice_client is not None:  # VoiceClientがあるがis_connectedがfalseの場合 -> 一度強制切断
                await voice_client.disconnect(force=True)
            voice_channel = interaction.user.voice.channel
            await voice_channel.connect()
            await interaction.response.send_message(embed=response.success(f"{voice_channel.name}に接続しました"), ephemeral=True)
            if voice_channel.type == discord.ChannelType.stage_voice and voice_channel.permissions_for(interaction.guild.me).manage_channels:
                await interaction.guild.me.edit(suppress=False)
        elif voice_client.channel.id != interaction.user.voice.channel.id:
            await voice_client.move_to(interaction.user.voice.channel)
            await interaction.response.send_message(embed=response.success(f"{interaction.user.voice.channel.name}に移動しました"), ephemeral=True)
        else:
            # await interaction.response.send_message(embed=response.warning(f"既に{interaction.user.voice.channel.name}に接続しています"))
            await interaction.response.send_message(embed=response.success(f"{interaction.user.voice.channel.name}に接続しています"), ephemeral=True)

    async def process(self, interaction: discord.Interaction, search: str, suppress: bool, server: Optional[int]) -> Union[int, discord.Embed]:
        """楽曲のデータ取得処理"""
        player = self.get_player(interaction) if server is None else self.players[server]
        async with interaction.channel.typing():
            if search.startswith(("http://", "https://")) and "list=" in search:  # playlist
                match = re.search("[a-zA-Z0-9_-]{34}", search)
                if match is not None:  # プレイリストのリンクは専用の形式に変換 / ミックスリストはそのままでOK
                    search = "https://www.youtube.com/playlist?list=" + match.group()
                data = await YTDLSource.create_source(search, loop=self.bot.loop, process=False)
            else:  # video, search
                data = await YTDLSource.create_source(search, loop=self.bot.loop)
        if data is None:
            return 0 if suppress else response.error(f"一致する検索結果はありませんでした:\n {search}")
        elif data["extractor"] in ["youtube", "youtube:search"]:  # URL指定または検索
            if data["extractor"] == "youtube:search":  # 検索
                if not data["entries"]:
                    return 0 if suppress else response.error(f"一致する検索結果はありませんでした:\n {search}")
                data = data["entries"][0]
            await player.queue.put(data)
            return 1 if suppress else response.success(f"{data['title']}を追加しました")
        elif data["extractor"] == "youtube:tab":  # プレイリスト
            meta_count = 0
            for meta in data["entries"]:
                if meta["duration"] is None:  # 削除された動画をスキップ
                    continue
                meta["webpage_url"] = "https://www.youtube.com/watch?v=" + meta["id"]
                await player.queue.put(meta)
                meta_count += 1
            return meta_count if suppress else response.success(f"{data['title']}から{meta_count}曲を追加しました")

    async def play(self, interaction: discord.Interaction, query: str, server: Optional[int] = None) -> discord.Message:
        """音楽の追加"""
        await interaction.response.send_message(embed=response.normal("読込中..."))
        query = [q for q in query.split("\n") if q != ""]
        res_msg: discord.Message
        if len(query) == 1:
            embed = await self.process(interaction, query[0], False, server)
            res_msg = await interaction.channel.send(embed=embed)
        else:  # 複数曲対応
            count = 0
            for search in query:
                count += await self.process(interaction, search, True, server)
            res_msg = await interaction.channel.send(embed=response.success(f"合計{count}曲を追加しました"))
        wait_msg = await interaction.original_message()
        await wait_msg.delete()
        return res_msg

    async def disconnect(self, interaction: discord.Interaction):
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = interaction.guild.voice_client
        msg: discord.Message
        if not voice_client:  # 単体以外では起こらないはずだが、強制切断の判断に必要なので残す
            msg = await interaction.channel.send(embed=response.error("BOTはまだボイスチャンネルに接続していません"))
        elif not voice_client.is_connected():  # VoiceClientがあるがis_connectedがfalseの場合 -> 一度強制切断
            await voice_client.disconnect(force=True)
            msg = await interaction.channel.send(embed=response.error("異常な状況が検出されたので強制的に切断しました"))
        else:
            voice_channel: discord.StageChannel = interaction.guild.voice_client.channel
            if voice_channel.type == discord.ChannelType.stage_voice and voice_channel.permissions_for(interaction.guild.me).manage_channels and voice_channel.instance is not None:
                await voice_channel.instance.delete()
            await voice_client.disconnect()
            msg = await interaction.channel.send(embed=response.success("切断しました"))
        await msg.delete(delay=10)

    async def skip(self, interaction: discord.Interaction):
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            return await interaction.channel.send(embed=response.error("現在再生中の音楽はありません"))
        voice_client.stop()
        return await interaction.channel.send(embed=response.success("音楽をスキップしました"))

    async def shuffle(self, interaction: discord.Interaction):
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.channel.send(embed=response.error("現在予約された曲はありません"))
        random.shuffle(player.queue._queue)
        return await interaction.channel.send(embed=response.success("予約された曲をシャッフルしました"))


async def setup(bot: souffle.Souffle):
    await bot.add_cog(Music(bot))
