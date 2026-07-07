import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from discord import app_commands
import os
import threading
import random
from datetime import datetime
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
intents.members = True
intents.voice_states = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_message(message):
    if message.author.bot or message.channel.id not in CROSS_CHAT_CHANNELS:
        await bot.process_commands(message)
        return

    # 針對目標頻道發送訊息
    for channel_id in CROSS_CHAT_CHANNELS:
        if channel_id != message.channel.id:
            target_channel = bot.get_channel(channel_id)
            if target_channel:
                # 1. 取得或建立 Webhook
                webhooks = await target_channel.webhooks()
                # 尋找機器人自己創建的 Webhook
                webhook = next((w for w in webhooks if w.name == "CrossChat"), None)
                
                if not webhook:
                    # 如果沒有就建立一個
                    webhook = await target_channel.create_webhook(name="CrossChat")
                
                # 2. 透過 Webhook 發送訊息 (模仿使用者頭像與名字)
                await webhook.send(
                    content=message.content,
                    username=f"{message.author.display_name} ({message.guild.name})",
                    avatar_url=message.author.avatar.url if message.author.avatar else None
                )
    
    await bot.process_commands(message)

# --- 語音投影邏輯 ---
MY_ID = 1150359752359038986
TARGET_VOICE_CHANNELS = [1349216822272065556, 1349216872138149888] # 柏仔群語音
PROJECTION_CHANNEL_ID = 1517214446844645397 # 頻道 ID
# 如果需要機器人加入的語音房，填入 ID，否則設為 None
BOT_JOIN_CHANNEL_ID = 1515416118645493770

# --- 時間頻道邏輯 ---
TIME_CHANNEL_ID = 1246736970013741077

# --- 每日音樂挑戰邏輯 ---
MUSIC_CHANNEL_ID = 1524036557948977152
current_music_msg_id = None  # 用於追蹤最新的一則題目
MUSIC_THEMES = [
# 語言分類主題
    "中文歌 🇹🇼",
    "英文歌 🇺🇸",
    "日文歌 🇯🇵",
    
    # 情感與場景主題
    "失戀時聽的歌 💔",
    "以前最喜歡的歌 📻",
    "最近循環播放的歌 🔁",
    "冷門的歌 💎",
    "讓你充滿能量的歌 ⚡",
    "最適合在下雨天聽的歌 🌧️",
    "你第一首聽的歌 🍼",
    "最符合你現在心情的歌 💭",
    "讓你想起過去的歌 🎞️",
    "最適合在夏天聽的歌 ☀️",
    "這生必聽的歌 ❤️"
]

# 建立一個每 15 秒檢查一次的任務
@tasks.loop(seconds=15)
async def check_my_status():
    projection_channel = bot.get_channel(PROJECTION_CHANNEL_ID)
    if not projection_channel:
        return

    found = False
    # 遍歷機器人所在的「所有」伺服器，尋找你
    for guild in bot.guilds:
        member = guild.get_member(MY_ID)
        if member and member.voice and member.voice.channel:
            # 偵測到你在語音中！
            count = len(member.voice.channel.members)
            new_name = f"🔴｜瑪芬柏仔群 {count}人"
            
            if projection_channel.name != new_name:
                await projection_channel.edit(name=new_name)
            found = True
            break
    
    # 如果所有伺服器都找不到你在語音
    if not found:
        if projection_channel.name != "🟢｜瑪芬在群裡":
            await projection_channel.edit(name="🟢｜瑪芬在群裡")

@tasks.loop(minutes=30)
async def update_time_channel():
    channel = bot.get_channel(TIME_CHANNEL_ID)
    if not channel:
        return

    # 獲取當前小時 (注意：Render 的伺服器時間預設為 UTC，你可能需要 +8 小時調整為台灣時間)
    # 如果發現時間不對，請將 now = datetime.utcnow().hour + 8 修改為適合的時區
    now = datetime.utcnow().hour + 8
    if now >= 24: now -= 24
    
    # 設定咖啡與啤酒的時段
    # 假設 06:00 - 18:00 為咖啡時段，18:00 - 06:00 為啤酒時段
    if 6 <= now < 18:
        new_name = "☕｜來一杯咖啡"
    else:
        new_name = "🍺｜來一杯啤酒"

    # 只有名字不同時才修改，避免 API 限制
    if channel.name != new_name:
        await channel.edit(name=new_name)

class MusicSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=theme, value=theme) for theme in MUSIC_THEMES]
        super().__init__(placeholder="請選擇今日的音樂主題...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # 僅對點選者顯示 (ephemeral=True)，頻道內完全不會出現訊息
        await interaction.response.send_message(f"🎵 已選定主題：**{self.values[0]}**\n請現在分享你的歌曲！", ephemeral=True)

class MusicView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MusicSelect())

@bot.tree.command(name="music", description="在當前頻道發布音樂主題選單")
@app_commands.checks.has_permissions(administrator=True)
async def slash_music(interaction: discord.Interaction):
    # 直接在指令輸入的頻道發送選單
    embed = discord.Embed(
        title="🎵 每日一曲",
        description="請選擇今日的音樂主題，分享你的歌：",
        color=discord.Color.gold()
    )
    # 發送選單
    await interaction.channel.send(embed=embed, view=MusicView())
    
    # 指令發送成功後的短暫回饋 (僅管理員可見)
    await interaction.response.send_message("✅ 選單已發送。", ephemeral=True)

# 在 on_ready 啟動這個任務
@bot.event
async def on_ready():
    print("機器人已啟動...")
    await bot.tree.sync()
    check_my_status.start()
    update_time_channel.start()

if __name__ == "__main__":
    # 啟動 Web Server 線程
    threading.Thread(target=run_web).start()
    bot.run(TOKEN)
