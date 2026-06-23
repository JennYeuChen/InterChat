import discord
from discord.ext import commands
from collections import Counter
import re
import os
import threading
from flask import Flask
from datetime import datetime

# 1. 為了 Render 24 小時不休眠的 Web Server
app = Flask(__name__)
@app.route('/')
def home():
    return "Emoji Counter Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# 2. 機器人初始化
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 抓取 Emoji 的正則表達式
EMOJI_REGEX = re.compile(r'<a?:[a-zA-Z0-9_]+:([0-9]+)>')

@bot.event
async def on_ready():
    print(f"機器人已上線：{bot.user}")
    print("功能：!count_emojis 統計歷史 Emoji")

@bot.command()
@commands.has_permissions(administrator=True)
async def count_emojis(ctx):
    await ctx.send("⏳ 正在深層挖掘歷史數據，這可能需要幾分鐘，請稍候...")
    
    emoji_counts = Counter()
    # 這裡抓的是伺服器內定義的所有自訂 Emoji
    server_emojis = {str(e.id): e for e in ctx.guild.emojis}
    
    total_channels = len(ctx.guild.text_channels)
    processed = 0
    
    # 遍歷所有文字頻道
    for channel in ctx.guild.text_channels:
        permissions = channel.permissions_for(ctx.guild.me)
        if not permissions.read_message_history:
            continue
            
        try:
            # 遍歷該頻道所有歷史訊息
            async for message in channel.history(limit=None):
                if message.author.bot:
                    continue
                
                # 抓取 Emoji ID
                matches = EMOJI_REGEX.findall(message.content)
                for emoji_id in matches:
                    if emoji_id in server_emojis:
                        emoji_counts[emoji_id] += 1
        except Exception as e:
            print(f"頻道 {channel.name} 統計異常: {e}")
            
        processed += 1
        print(f"已處理 {processed}/{total_channels} 頻道...")

    if not emoji_counts:
        await ctx.send("❌ 沒有發現自訂 Emoji 的使用記錄。")
        return

    # 輸出排行榜 (取前 15 名)
    top_emojis = emoji_counts.most_common(15)
    result = "🏆 **自訂 Emoji 使用排行榜** 🏆\n"
    for i, (eid, count) in enumerate(top_emojis, 1):
        emoji = server_emojis[eid]
        result += f"{i}. {emoji} `{emoji.name}`: **{count} 次**\n"
        
    await ctx.send(result)

if __name__ == "__main__":
    # 同時啟動 Web Server 和 Bot
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
