import discord
from discord.ext import commands
from discord import app_commands

import asyncio
from async_timeout import timeout
import random
import re
import traceback2
from typing import Union
import yt_dlp as youtube_dl

import response

ytdl_options = {
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
    'cookiefile': 'cookies.txt'
}

ffmpeg_options = {
    'before_options': '-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_options)


class YTDLSource(discord.PCMVolumeTransformer):
    """youtube-dl操作"""

    def __init__(self, source, *, data):
        super().__init__(source)
        self.data = data

        self.title = data["title"]
        self.url = data["webpage_url"]
        self.duration = data["duration"]

    def __getitem__(self, item):
        return self.data[item]

    @classmethod
    async def create_source(cls, search: str, *, loop, process=True):
        """動画データの取得"""
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


class Player:
    """再生操作全般を行うプレイヤー"""

    def __init__(self, interaction):
        self.bot = interaction.client
        self.guild = interaction.guild
        self.channel = interaction.channel
        self.volume = 1
        self.loop = 0  # 0: off / 1: loop / 2: loop_queue
        self.queue = asyncio.Queue()
        self.next = asyncio.Event()
        self.current = None
        self.menu = None
        self.task = interaction.client.loop.create_task(
            self.player_loop()
        )

    async def player_loop(self):
        """音楽再生のメインループ"""
        while True:
            self.next.clear()
            try:
                if len(self.queue._queue) == 0 and self.menu is not None:
                    await self.menu.update()  # 予約曲が0でメニューがある場合
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
            await self.next.wait()
            source.cleanup()
            self.current = None
            if self.loop == 2:
                await self.queue.put(data)
            elif self.loop == 1:
                self.queue._queue.appendleft(data)

    def destroy(self, guild):
        return self.bot.loop.create_task(guild.voice_client.disconnect())


class Request(discord.ui.Modal, title="音楽の追加"):
    text = discord.ui.TextInput(
        label='再生したい曲名またはURLを入力してください',
        style=discord.TextStyle.long,
        placeholder='例) 夜に駆ける, https://youtu.be/TA5OFS_xX0c'
    )

    def __init__(self, interaction):
        super().__init__()
        self.cog = interaction.client.get_cog("Music")

    async def on_submit(self, interaction: discord.Interaction):
        """成功した場合、音楽の再生処理"""
        msg = await self.cog.play(interaction, self.text.value)
        await self.cog.get_player(interaction).menu.update()
        await msg.delete(delay=3)

    async def on_error(self, error: Exception, interaction: discord.Interaction):
        """失敗した場合、エラーメッセージを送信"""
        msg = await interaction.channel.send(embed=response.error(f"処理中に予期しないエラーが発生しました。\n```py{error}```"))  # on_submitで既にresponseを使用した場合エラー
        await msg.delete(delay=3)


class MenuView(discord.ui.View):
    """playerコマンドの再生メニュー用Viewクラス"""

    def __init__(self, interaction):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.cog = interaction.client.get_cog("Music")

    @discord.ui.button(emoji="➕")
    async def request(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(Request(interaction))

    @discord.ui.button(emoji="⏸")
    async def play(self, button: discord.ui.Button, interaction: discord.Interaction):
        voice_client = self.interaction.guild.voice_client
        embed: discord.Embed
        if not voice_client or not voice_client.is_connected():  # 未接続
            embed = response.error("現在再生中の音楽はありません")
        elif voice_client.is_playing():
            button.emoji = "▶"
            button.style = discord.ButtonStyle.green
            voice_client.pause()
            embed = response.success("音楽の再生を一時停止しました")
        elif voice_client.is_paused():
            button.emoji = "⏸"
            button.style = discord.ButtonStyle.grey
            voice_client.resume()
            embed = response.success("音楽の再生を再開しました")
        else:
            embed = response.error("現在再生中の音楽はありません")
        msg = await self.interaction.channel.send(embed=embed)
        await self.update(msg)

    @discord.ui.button(emoji="⏭")
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction):
        msg = await self.cog.skip(interaction)
        await self.update(msg)

    @discord.ui.button(emoji="🔄")
    async def loop(self, button: discord.ui.Button, interaction: discord.Interaction):
        player = self.cog.get_player(interaction)
        embed: discord.Embed
        if player.loop == 0:
            player.loop += 1
            button.emoji = "🔂"
            button.style = discord.ButtonStyle.green
            embed = response.success("現在再生中の曲の繰り返しを有効にしました")
        elif player.loop == 1:
            player.loop += 1
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.green
            embed = response.success("予約された曲全体の曲の繰り返しを有効にしました")
        else:  # 2
            player.loop = 0
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.grey
            embed = response.success("曲の繰り返しを無効にしました")
        msg = await interaction.channel.send(embed=embed)
        await self.update(msg)

    @discord.ui.button(emoji="🔀")
    async def shuffle(self, button: discord.ui.Button, interaction: discord.Interaction):
        msg = await self.cog.shuffle(interaction)
        await self.update(msg)

    @discord.ui.button(label="■", style=discord.ButtonStyle.red)
    async def stop_(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.cog.disconnect(interaction)

    async def update(self, msg):  # 各アクション実行後に画面更新&メッセージ削除
        await self.cog.get_player(self.interaction).menu.update(self)
        await msg.delete(delay=3)


class Menu:
    """playerコマンドの再生メニュー"""

    def __init__(self, interaction):
        self.interaction = interaction
        self.bot = interaction.client
        self.channel = interaction.channel
        self.msg = None
        self.view = None

    async def initialize(self):
        self.view = MenuView(self.interaction)
        self.msg = await self.channel.send("読込中...", view=self.view)
        await self.update()

    async def update(self, view=None):
        player = self.bot.get_cog("Music").get_player(self.interaction)
        voice_client = self.interaction.guild.voice_client
        text = ""
        if voice_client.source is not None:
            text += f"\n再生中:\n [{voice_client.source.title}]({voice_client.source.url}) | {duration_to_text(voice_client.source.duration)}\n"
            text += "-------------------------------------------------"
        elif player.queue.empty():
            text += "まだ曲が追加されていません"

        for i in range(min(len(player.queue._queue), 10)):  # 最大10曲
            d = player.queue._queue[i]
            text += f"\n{i + 1}. [{d['title']}]({d['webpage_url']}) | {duration_to_text(d['duration'])}"
        if len(player.queue._queue) > 10:
            text += "\n等..."

        embed = discord.Embed(description=text, color=discord.Color.blurple())
        embed.set_footer(text=f"\n\n現在{len(player.queue._queue)}曲が予約されています")

        if view is None:
            await self.msg.edit(content=None, embed=embed)
        else:
            await self.msg.edit(content=None, embed=embed, view=view)

    async def destroy(self):
        self.view.stop()
        self.view.clear_items()
        await self.msg.delete()


def duration_to_text(seconds):
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


class Music(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.players = {}

    def get_player(self, interaction):
        try:
            player = self.players[interaction.guild.id]
        except KeyError:
            player = Player(interaction)
            self.players[interaction.guild.id] = player
        return player

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel is not None and after.channel is None:  # 退出
            bot_member = member.guild.get_member(self.bot.user.id)
            if member == bot_member:  # botの退出
                try:
                    self.players[member.guild.id].task.cancel()
                    if self.players[member.guild.id].menu is not None:
                        self.bot.loop.create_task(self.players[member.guild.id].menu.destroy())
                    del self.players[member.guild.id]
                except:
                    pass
            # MEMO: memberインテントが必要
            # 自動切断
            elif bot_member in before.channel.members:  # BOT接続しているVC
                voice_members = before.channel.members
                real_members = discord.utils.get(voice_members, bot=False)
                if len(voice_members) == 1 or real_members is None:
                    # if member.guild.id in self.players:
                    #     player = self.get_player(member)
                    #     await player.channel.send("")
                    await member.guild.voice_client.disconnect()

    @app_commands.command(name="player", description="音楽再生操作パネルを起動します")
    async def player_(self, interaction: discord.Interaction):
        # VCに接続していることを確認
        # if interaction.guild.voice_client is None: # interaction消費のため既に接続している旨のメッセージを送信
        if await self.join(interaction):
            return
        player = self.get_player(interaction)
        if player.menu is not None:  # 前のメニューを破棄
            old_menu = player.menu  # destroy()してからmenuがNoneになるまでの間にplayer_loopがメッセージを編集しようとするのを防ぐ
            player.menu = None  # 先にNone化
            await old_menu.destroy()
        menu = Menu(interaction)
        await menu.initialize()  # 初期化完了後にメニュー登録
        player.menu = menu

    async def join(self, interaction: discord.Interaction):
        """VCに接続"""
        # if interaction.guild.id not in self.bot.cache_guilds:
        #     embed = discord.Embed(
        #         description=f"負荷対策のため音楽機能はサーバーごとの承認制になっています。\n__**ミルクチョコプレイヤーの方**__は基本誰でも許可しますので、\n1. __上の番号__(コピペでok)\n"
        #                     f"2. __ミルクチョコをしていることがわかるもの(ゲームのスクショやツイッターなど)__\nとともに[公式サーバー](https://discord.gg/h2ZNX9mSSN)の<#887981017539944498>でお伝えください！",
        #         color=discord.Color.blue()
        #     )
        #     return await interaction.channel.send(f"{interaction.guild.id}\nhttps://discord.gg/h2ZNX9mSSN", embed=embed)

        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = interaction.guild.voice_client
        if interaction.user.voice is None:
            await interaction.response.send_message(embed=response.error("先にボイスチャンネルに接続してください!"))
            return True
        elif voice_client is None or not voice_client.is_connected():
            if voice_client is not None:  # VoiceClientがあるがis_connectedがfalseの場合 -> 一度強制切断
                await voice_client.disconnect(force=True)
            voice_channel = interaction.user.voice.channel
            await voice_channel.connect()
            await interaction.response.send_message(embed=response.success(f"{voice_channel.name}に接続しました"))
            if voice_channel.type == discord.ChannelType.stage_voice and voice_channel.permissions_for(interaction.guild.me).manage_channels:
                await interaction.guild.me.edit(suppress=False)
        elif voice_client.channel.id != interaction.user.voice.channel.id:
            await voice_client.move_to(interaction.user.voice.channel)
            await interaction.response.send_message(embed=response.success(f"{interaction.user.voice.channel.name}に移動しました"))
        else:
            # await interaction.response.send_message(embed=response.warning(f"既に{interaction.user.voice.channel.name}に接続しています"))
            await interaction.response.send_message(embed=response.success(f"{interaction.user.voice.channel.name}に接続しています"))

    async def process(self, interaction: discord.Interaction, search: str, suppress: bool):
        """楽曲のデータ取得処理"""
        player = self.get_player(interaction)
        async with interaction.channel.typing():
            if search.startswith(("http://", "https://")) and "list=" in search:  # playlist
                match = re.search("[a-zA-Z0-9_-]{34}", search)
                if match is not None:  # プレイリストのリンクは専用の形式に変換 / ミックスリストはそのままでOK
                    search = "https://www.youtube.com/playlist?list=" + match.group()
                data = await YTDLSource.create_source(search, loop=self.bot.loop, process=False)
            else:  # video, search
                data = await YTDLSource.create_source(search, loop=self.bot.loop)
        if data is None:
            return 0 if suppress else await interaction.channel.send(embed=response.error(f"一致する検索結果はありませんでした:\n {search}"))
        elif data["extractor"] in ["youtube", "youtube:search"]:  # URL指定または検索
            if data["extractor"] == "youtube:search":  # 検索
                if not data["entries"]:
                    return 0 if suppress else await interaction.channel.send(embed=response.error(f"一致する検索結果はありませんでした:\n {search}"))
                data = data["entries"][0]
            await player.queue.put(data)
            return 1 if suppress else await interaction.channel.send(embed=response.success(f"{data['title']}を追加しました"))
        elif data["extractor"] == "youtube:tab":  # プレイリスト
            meta_count = 0
            for meta in data["entries"]:
                meta["webpage_url"] = "https://www.youtube.com/watch?v=" + meta["id"]
                await player.queue.put(meta)
                meta_count += 1
            return meta_count if suppress else await interaction.channel.send(embed=response.success(f"{data['title']}から{meta_count}曲を追加しました"))

    async def play(self, interaction: discord.Interaction, query: str):
        """音楽の追加"""
        # if interaction.guild.voice_client is None:
        #     if await self.join(interaction):
        #         return
        await interaction.response.send_message(embed=response.normal("読込中..."))
        query = [q for q in query.split("\n") if q != ""]
        ret_msg: discord.Message
        if len(query) == 1:
            res_msg = await self.process(interaction, query[0], False)
        else:  # 複数曲対応
            # TODO: 途中で切断処理が入った場合に停止する
            count = 0
            for search in query:
                count += await self.process(interaction, search, True)
            res_msg = await interaction.channel.send(embed=response.success(f"合計{count}曲を追加しました"))
        wait_msg = await interaction.original_message()
        await wait_msg.delete()
        return res_msg

    async def disconnect(self, interaction: discord.Interaction):
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = interaction.guild.voice_client
        if not voice_client:  # 単体以外では起こらないはずだが、強制切断の判断に必要なので残す
            return await interaction.channel.send(embed=response.error("BOTはまだボイスチャンネルに接続していません"))
        elif not voice_client.is_connected():  # VoiceClientがあるがis_connectedがfalseの場合 -> 一度強制切断
            await voice_client.disconnect(force=True)
            return await interaction.channel.send(embed=response.error("異常な状況が検出されたので強制的に切断しました"))
        await voice_client.disconnect()
        await interaction.channel.send(embed=response.success("切断しました"))

    async def skip(self, interaction: discord.Interaction):
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            return await interaction.channel.send(embed=response.error("現在再生中の音楽はありません"))
        voice_client.stop()
        return await interaction.channel.send(embed=response.success("音楽をスキップしました"))

    async def shuffle(self, interaction: discord.Interaction):
        voice_client: Union[discord.VoiceClient, discord.VoiceProtocol] = interaction.guild.voice_client
        # if not voice_client or not voice_client.is_connected():
        #     return await interaction.channel.send(embed=response.error("BOTはまだボイスチャンネルに接続していません"))
        player = self.get_player(interaction)
        if player.queue.empty():
            return await interaction.channel.send(embed=response.error("現在予約された曲はありません"))
        random.shuffle(player.queue._queue)
        return await interaction.channel.send(embed=response.success("予約された曲をシャッフルしました"))


async def setup(bot):
    await bot.add_cog(Music(bot))
