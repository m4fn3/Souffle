import asyncio
from contextlib import redirect_stdout
import datetime
import discord
from discord.ext import commands
from discord import app_commands
import io
import os
import pickle
import psutil
import subprocess
import time
import textwrap
import traceback2
from typing import Literal

import souffle
import response

dev_guild = discord.Object(id=565434676877983772)
admin = [513136168112750593, 519760564755365888, 561359054165901347, 585351496523186187, 822814328238506014]


class ExeInput(discord.ui.Modal, title="コード実行"):
    code = discord.ui.TextInput(label='プログラムを入力', style=discord.TextStyle.long)

    def __init__(self, bot: souffle.Souffle):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):

        env = {
            'bot': self.bot,
            'interaction': interaction,
            'channel': interaction.channel,
            'guild': interaction.guild,
            'message': interaction.message
        }
        env.update(globals())
        code = self.code.value
        if code.startswith('```') and code.endswith('```'):
            code = '\n'.join(code.split('\n')[1:-1])
        code = code.strip("` \n")
        stdout = io.StringIO()
        to_compile = f'async def func():\n{textwrap.indent(code, "  ")}'
        result: str
        try:
            exec(to_compile, env)
            func = env['func']
            try:
                with redirect_stdout(stdout):
                    ret = await func()
            except Exception as e:
                value = stdout.getvalue()
                result = f'{value}{traceback2.format_exc()}'
            else:
                value = stdout.getvalue()
                try:
                    await interaction.message.add_reaction('\u2705')
                except:
                    pass

                if ret is None:
                    result = f"{value}" if value else ""
                else:
                    result = f"{value}{ret}"
        except Exception as e:
            result = f"{e.__class__.__name__}: {e}"
        await interaction.response.send_message(code, embed=discord.Embed(description=f"```py\n{result}\n```"), ephemeral=True)


class Developer(commands.Cog):
    """開発者用コマンド"""

    def __init__(self, bot: souffle.Souffle):
        """初期化処理"""
        self.bot = bot

    @app_commands.command(description="[管理者用] 音楽機能の利用を承認します")
    @app_commands.guilds(dev_guild)
    async def accept(self, interaction: discord.Interaction, guild_id: str):
        """利用承認"""
        if interaction.user.id in admin:
            try:
                guild_id = int(guild_id)
            except:
                return await interaction.response.send_message(embed=response.error("無効なサーバーIDです"))
            if guild_id not in self.bot.verified_guilds:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    await interaction.response.send_message(embed=response.error("そのサーバーに参加していません"))
                else:
                    self.bot.verified_guilds.add(guild_id)
                    await interaction.response.send_message(embed=response.success(f"{guild.name}での利用を承認しました"))
                    with open('guilds.pickle', 'wb') as f:
                        pickle.dump(self.bot.verified_guilds, f)
            else:
                await interaction.response.send_message(embed=response.warning("そのサーバーはすでに承認されています"))

    @app_commands.command(description="[管理者用] 音楽機能の利用を拒否します")
    @app_commands.guilds(dev_guild)
    async def refuse(self, interaction: discord.Interaction, guild_id: str):
        """利用拒否"""
        if interaction.user.id in admin:
            try:
                guild_id = int(guild_id)
            except:
                return await interaction.response.send_message(embed=response.error("無効なサーバーIDです"))
            if guild_id in self.bot.verified_guilds:
                guild = self.bot.get_guild(guild_id)
                if guild is None:
                    self.bot.verified_guilds.discard(guild_id)
                    await interaction.response.send_message(embed=response.warning("そのサーバーでの使用を拒否しました"))
                else:
                    self.bot.verified_guilds.discard(guild_id)
                    await interaction.response.send_message(embed=response.success(f"{guild.name}での利用を拒否しました"))
                with open('guilds.pickle', 'wb') as f:
                    pickle.dump(self.bot.verified_guilds, f)
            else:
                await interaction.response.send_message(embed=response.warning("そのサーバーはまだ承認されていません"))

    @app_commands.command(description="[管理者用] BOTの稼働情報を表示します")
    @app_commands.guilds(dev_guild)
    async def process(self, interaction: discord.Interaction):
        """稼働情報の表示"""
        if interaction.user.id in admin:
            td = datetime.timedelta(seconds=int(time.time() - self.bot.uptime))
            m, s = divmod(td.seconds, 60)
            h, m = divmod(m, 60)
            d = td.days
            uptime = f"{d}d {h}h {m}m {s}s"
            cpu_per = psutil.cpu_percent()
            mem_total = psutil.virtual_memory().total / 10 ** 9
            mem_used = psutil.virtual_memory().used / 10 ** 9
            mem_per = psutil.virtual_memory().percent
            swap_total = psutil.swap_memory().total / 10 ** 9
            swap_used = psutil.swap_memory().used / 10 ** 9
            swap_per = psutil.swap_memory().percent
            guilds = len(self.bot.guilds)
            users = len(self.bot.users)
            vcs = len(self.bot.voice_clients)
            text_channels = 0
            voice_channels = 0
            for channel in self.bot.get_all_channels():
                if isinstance(channel, discord.TextChannel):
                    text_channels += 1
                elif isinstance(channel, discord.VoiceChannel):
                    voice_channels += 1
            latency = self.bot.latency
            try:
                temp = [str(obj.current) + "℃" for key in psutil.sensors_temperatures() for obj in psutil.sensors_temperatures()[key]]
            except:
                temp = ["N/A"]
            process = psutil.Process(os.getpid())
            using_mem = f"{(process.memory_info().rss // 1000000):.1f} MB"
            embed = discord.Embed(title="Process")
            embed.add_field(name="Server",
                            value=f"```yaml\nCPU: [{cpu_per}%]\nMemory: [{mem_per}%] {mem_used:.2f}GiB / {mem_total:.2f}GiB\nSwap: [{swap_per}%] {swap_used:.2f}GiB / {swap_total:.2f}GiB\nTemperature: {','.join(temp)}\nUsingMem: {using_mem}```",
                            inline=False)
            embed.add_field(name="Discord", value=f"```yaml\nServers: {guilds}\nTextChannels: {text_channels}\nVoiceChannels: {voice_channels}\nUsers: {users}\nConnectedVC: {vcs}```", inline=False)
            embed.add_field(name="Run", value=f"```yaml\nCommandRuns: {self.bot.cmd_count}\nUptime: {uptime}\nLatency: {latency:.2f}[s]\n```")
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(description="[管理者用] プログラムを再読み込みします")
    @app_commands.guilds(dev_guild)
    async def reload(self, interaction: discord.Interaction, cog: Literal["music", "developer"]):
        if interaction.user.id in admin:
            try:
                if cog == "music":
                    players = self.bot.get_cog("Music").players
                    await self.bot.reload_extension("music")
                    self.bot.get_cog("Music").players = players
                else:
                    await self.bot.reload_extension(cog)
            except:
                await interaction.response.send_message(embed=response.error(f"{cog}の再読み込みに失敗しました\n{traceback2.format_exc()}."), ephemeral=True)
            else:
                await interaction.response.send_message(embed=response.success(f"{cog}の再読み込みに成功しました"), ephemeral=True)

    @app_commands.command(description="[管理者用] シェルコマンドを実行します")
    @app_commands.guilds(dev_guild)
    async def cmd(self, interaction: discord.Interaction, cmd: str):
        if interaction.user.id in admin:
            output = await self.run_subprocess(cmd, loop=self.bot.loop)
            try:
                await interaction.response.send_message("\n".join(output), ephemeral=True)
            except:
                await interaction.response.send_message(file=discord.File(fp=io.StringIO("\n".join(output)), filename="output.txt"), ephemeral=True)

    @app_commands.command(description="[管理者用] スラッシュコマンドの同期を行います")
    @app_commands.guilds(dev_guild)
    async def sync(self, interaction: discord.Interaction):
        if interaction.user.id in admin:
            await self.bot.tree.sync()
            await self.bot.tree.sync(guild=dev_guild)
            await interaction.response.send_message(embed=response.success("同期に成功しました"), ephemeral=True)

    @app_commands.command(description="[管理者用] 任意のプログラムを実行します")
    @app_commands.guilds(dev_guild)
    async def exe(self, interaction: discord.Interaction):
        if interaction.user.id in admin:
            await interaction.response.send_modal(ExeInput(self.bot))

    async def run_subprocess(self, cmd: str, loop=None):
        loop = loop or asyncio.get_event_loop()
        try:
            process = await asyncio.create_subprocess_shell(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except NotImplementedError:
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True) as process:
                try:
                    result = await loop.run_in_executor(None, process.communicate)
                except Exception:
                    def kill():
                        process.kill()
                        process.wait()

                    await loop.run_in_executor(None, kill)
                    raise
        else:
            result = await process.communicate()

        return [res.decode('utf-8') for res in result]


async def setup(bot: souffle.Souffle):
    await bot.add_cog(Developer(bot))
