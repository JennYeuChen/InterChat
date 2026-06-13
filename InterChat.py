import discord
from discord.ext import commands
import os
import threading
from flask import Flask

# Flask 網頁伺服器，用來維持 Render 活躍
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# 機器人邏輯
TOKEN = os.environ.get("DISCORD_TOKEN")
CROSS_CHAT_CHANNELS = [int(cid) for cid in os.environ.get("CROSS_CHAT_CHANNELS", "").split(",") if cid]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_message(message):
    if message.author.bot or message.channel.id not in CROSS_CHAT_CHANNELS:
        await bot.process_commands(message)
        return

    for channel_id in CROSS_CHAT_CHANNELS:
        if channel_id != message.channel.id:
            target_channel = bot.get_channel(channel_id)
            if target_channel:
                embed = discord.Embed(description=message.content, color=discord.Color.green())
                embed.set_author(name=f"{message.author.display_name} @ {message.guild.name}", 
                                 icon_url=message.author.avatar.url if message.author.avatar else None)
                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)
                await target_channel.send(embed=embed)
    await bot.process_commands(message)

if __name__ == "__main__":
    # 啟動 Web Server 線程
    threading.Thread(target=run_web).start()
    bot.run(TOKEN)
