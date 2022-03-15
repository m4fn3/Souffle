""" git+git://github.com/Rapptz/discord.py.git@6dd8845e4f38f22e226883234d369d43c7629f1a (v10使用) - メッセージ読み取り不可"""
import logging
import os
from dotenv import load_dotenv

import discord

from souffle import Souffle

load_dotenv(verbose=True)
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

TOKEN = os.getenv("TOKEN")
PREFIX = "."

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.typing = False
    intents.members = True
    client = Souffle(PREFIX, status=discord.Status.idle, intents=intents)
    client.run(TOKEN)
