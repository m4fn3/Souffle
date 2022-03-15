import datetime
import discord
from discord.ext import commands
from discord import app_commands
import os
import pickle
import psutil
import time

import souffle
import response

dev_guild = discord.Object(id=565434676877983772)
admin = [513136168112750593, 519760564755365888, 561359054165901347, 585351496523186187, 822814328238506014]


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
            embed.add_field(name="Run", value=f"```yaml\nUptime: {uptime}\nLatency: {latency:.2f}[s]\n```")
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: souffle.Souffle):
    await bot.add_cog(Developer(bot))
