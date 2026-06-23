import discord
from discord.ext import commands, tasks
import os
import threading
from flask import Flask
from datetime import datetime
from collections import Counter
import re

# 1. 網頁伺服器：保持 Render 活躍
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is alive!"

def run_web():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

# 2. 機器人初始化
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 配置參數
MY_ID = 1150359752359038986
PROJECTION_CHANNEL_ID = 1517214446844645397
TIME_CHANNEL_ID = 1246736970013741077
EMOJI_TARGET_CHANNEL = 1231050943663964195
EMOJI_REGEX = re.compile(r'<a?:[a-zA-Z0-9_]+:([0-9]+)>')

# 3. 任務：咖啡與啤酒時鐘
@tasks.loop(minutes=30)
async def update_time_channel():
    channel = bot.get_channel(TIME_CHANNEL_ID)
    if not channel: return

    # 台灣時間調整
    now = datetime.utcnow().hour + 8
    if now >= 24: now -= 24
    
    new_name = "☕｜來一杯咖啡" if 6 <= now < 18 else "🍺｜來一杯啤酒"
    if channel.name != new_name:
        await channel.edit(name=new_name)

# 4. 任務：語音狀態投影 (強制偵測版)
@tasks.loop(seconds=20)
async def smart_projection():
    projection_channel = bot.get_channel(PROJECTION_CHANNEL_ID)
    if not projection_channel: return

    found_you = False
    for guild in bot.guilds:
        member = guild.get_member(MY_ID)
        if member and member.voice and member.voice.channel:
            count = len(member.voice.channel.members)
            await projection_channel.edit(name=f"🔴｜瑪芬遠征中 ({count}人)")
            found_you = True
            break
            
    if not found_you:
        await projection_channel.edit(name="🟢｜瑪芬在群裡")

# 5. Emoji 統計指令 (僅限管理員)
@bot.command()
@commands.has_permissions(administrator=True)
async def count_emojis(ctx):
    channel = bot.get_channel(EMOJI_TARGET_CHANNEL)
    if not channel:
        return await ctx.send("❌ 找不到統計頻道。")

    msg = await ctx.send("⏳ 正在統計歷史 Emoji，請稍候...")
    emoji_counts = Counter()
    server_emojis = {str(e.id): e for e in ctx.guild.emojis}
    
    async for message in channel.history(limit=None):
        if message.author.bot: continue
        matches = EMOJI_REGEX.findall(message.content)
        for emoji_id in matches:
            if emoji_id in server_emojis:
                emoji_counts[emoji_id] += 1

    if not emoji_counts:
        return await msg.edit(content="❌ 無 Emoji 紀錄。")

    top_emojis = emoji_counts.most_common(15)
    result = f"🏆 **<#{EMOJI_TARGET_CHANNEL}> Emoji 排行榜** 🏆\n"
    for i, (eid, count) in enumerate(top_emojis, 1):
        emoji = server_emojis[eid]
        result += f"{i}. {emoji} `{emoji.name}`: **{count} 次**\n"
    await msg.edit(content=result)

@bot.event
async def on_ready():
    print(f'機器人已上線: {bot.user}')
    update_time_channel.start()
    smart_projection.start()

if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
