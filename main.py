import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from discord import app_commands
import os
import json
import threading
import random
import asyncio
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
DATA_FOLDER = "data"
os.makedirs(DATA_FOLDER, exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 數字接龍資料 (記憶體版，重啟會歸零)
game_data = {
    "current_number": 0,
    "last_user_id": None
}
GAME_CHANNEL_ID = 1418474416198782987

# --- 語音投影邏輯 ---
MY_ID = 1150359752359038986
TARGET_VOICE_CHANNELS = [1349216822272065556, 1349216872138149888] # 柏仔群語音
PROJECTION_CHANNEL_ID = 1517214446844645397 # 頻道 ID
# 如果需要機器人加入的語音房，填入 ID，否則設為 None
BOT_JOIN_CHANNEL_ID = 1515416118645493770

# --- 時間頻道邏輯 ---
TIME_CHANNEL_ID = 1246736970013741077

# --- 統計頻道邏輯 ---
STATS_MEMBER_CHANNEL_ID = 1525140695533355129  # 統計人數
STATS_MSG_CHANNEL_ID = 1525140760012390631      # 統計今天訊息
user_levels = {}  # 存儲使用者等級與每日訊息計數

# --- 每日音樂挑戰邏輯 ---
MUSIC_CHANNEL_ID = 1524036557948977152
current_music_msg_id = None  # 音樂頻道中那則訊息的 ID
current_active_theme = None   # 當前被選中的主題文字
# 定義需要自動加入反應的頻道列表
REACTION_CHANNELS = [1524036557948977152, 1508029438972137552]

# 身分組對應表 (Emoji: ID)
ROLE_MAP = {
    "📊": 1524619988923584563,
    "🎁": 1524618968180985916,
    "🎉": 1524619035990298775,
    "🎸": 1524619113463414967,
    "❓": 1524619170111819961
}

class RoleButton(discord.ui.Button):
    def __init__(self, emoji, role_id, role_name):
        # 按鈕顯示文字直接設為身分組名稱
        super().__init__(label=role_name, style=discord.ButtonStyle.secondary, emoji=emoji, custom_id=f"role_{role_id}")
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            return await interaction.response.send_message("❌ 找不到該身分組。", ephemeral=True)
        
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(f"✅ 已取消 **{role.name}** 通知。", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ 已訂閱 **{role.name}** 通知。", ephemeral=True)

class RoleSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # 這裡將名稱傳入，直接對應顯示
        names = ["投票通知", "福利通知", "活動通知", "每日一曲通知", "每日一問通知"]
        for i, (emoji, role_id) in enumerate(ROLE_MAP.items()):
            self.add_item(RoleButton(emoji, role_id, names[i]))

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

@tasks.loop(minutes=2) 
async def update_stats_channels():
    # 更新成員人數頻道
    member_channel = bot.get_channel(1525140695533355129)
    if member_channel:
        count = member_channel.guild.member_count
        try: await member_channel.edit(name=f"👥｜成員：{count}")
        except: pass

    # 更新今日訊息頻道
    msg_channel = bot.get_channel(1525140760012390631)
    if msg_channel:
        total_today = sum(user.get("daily_msg", 0) for user in user_levels.values())
        try: await msg_channel.edit(name=f"💬｜訊息：{total_today}")
        except: pass

# 這是選單的回呼函式，負責更新主題並發送至音樂頻道
async def update_music_display(channel_id, theme):
    global current_music_msg_id, current_active_theme
    current_active_theme = theme
    channel = bot.get_channel(channel_id)
    if not channel: return

    # 刪除舊訊息
    if current_music_msg_id:
        try:
            old_msg = await channel.fetch_message(current_music_msg_id)
            await old_msg.delete()
        except: pass

    # 發送新的主題訊息 (無選單)
    embed = discord.Embed(
        title="🎵 今日音樂挑戰",
        description=f"目前的主題是：\n\n**{theme}**\n\n快來分享你的歌曲！",
        color=discord.Color.gold()
    )
    new_msg = await channel.send(embed=embed)
    current_music_msg_id = new_msg.id

class MusicSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=theme, value=theme) for theme in MUSIC_THEMES]
        super().__init__(placeholder="請選擇今日的音樂主題...", options=options)

    async def callback(self, interaction: discord.Interaction):
        # 1. 更新全域變數並通知音樂頻道
        await update_music_display(MUSIC_CHANNEL_ID, self.values[0])
        # 2. 回應發送指令的人
        await interaction.response.send_message(f"✅ 已將主題更新為：**{self.values[0]}**", ephemeral=True)

class MusicView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MusicSelect())

@bot.tree.command(name="music", description="呼叫音樂主題選單")
@app_commands.checks.has_permissions(administrator=True)
async def slash_music(interaction: discord.Interaction):
    # 選單直接在當前輸入指令的頻道發送
    await interaction.response.send_message("請選擇今日音樂主題：", view=MusicView(), ephemeral=True)

@bot.tree.command(name="setup_roles", description="[管理員] 發送純淨的身分組按鈕")
@app_commands.checks.has_permissions(administrator=True)
async def setup_roles(interaction: discord.Interaction):
    # 直接發送 view，不發送 embed 或任何文字內容
    await interaction.channel.send(view=RoleSetupView())
    # 回應指令發送者（只有自己看得到）
    await interaction.response.send_message("✅ 面板已發送。", ephemeral=True)

# 底部檢測任務 (負責維持音樂頻道乾淨)
@tasks.loop(seconds=30)
async def keep_music_on_bottom():
    global current_music_msg_id, current_active_theme
    # 如果還沒選過主題，就不要亂發訊息
    if current_active_theme is None: return
    
    channel = bot.get_channel(MUSIC_CHANNEL_ID)
    if not channel: return

    async for last_msg in channel.history(limit=1):
        # 如果最後一則不是機器人，就重發當前主題
        if last_msg.author.id != bot.user.id:
            try:
                if current_music_msg_id:
                    old_msg = await channel.fetch_message(current_music_msg_id)
                    await old_msg.delete()
            except: pass
            
            embed = discord.Embed(
                title="🎵 今日音樂挑戰",
                description=f"目前的主題是：\n\n**{current_active_theme}**\n\n快來分享你的歌曲！",
                color=discord.Color.gold()
            )
            new_msg = await channel.send(embed=embed)
            current_music_msg_id = new_msg.id

# --- 自動愛心反應邏輯 ---
@bot.event
async def on_message(message):
    # 避免機器人自己回應自己
    if message.author == bot.user:
        return

    # --- 數字接龍邏輯 ---
    if message.channel.id == GAME_CHANNEL_ID:
        content = message.content.strip()
        
        # 如果不是純數字，無視
        if not content.isdigit():
            pass
        else:
            guess = int(content)
            
            # 邏輯檢查
            is_correct = (guess == game_data["current_number"] + 1)
            is_not_last_user = (message.author.id != game_data["last_user_id"])
            
            if is_correct and is_not_last_user:
                # 接龍正確
                game_data["current_number"] = guess
                game_data["last_user_id"] = message.author.id
                await message.add_reaction("✅")
            else:
                # 接龍失敗 (數錯或是連發)
                reason = "自己連續接龍" if not is_not_last_user else "數錯了"
                await message.channel.send(f"{message.author.mention} 你他媽這個白癡連數數都不會 ({reason})！")
                # 重置遊戲
                game_data["current_number"] = 0
                game_data["last_user_id"] = None
                await message.channel.send("遊戲重置，從 1 開始。")

    # 更新每日訊息計數
    user_id = str(message.author.id)
    if user_id not in user_levels:
        user_levels[user_id] = {"daily_msg": 0, "level": 1, "total_msg": 0}
    user_levels[user_id]["daily_msg"] += 1
    user_levels[user_id]["total_msg"] += 1

    # 檢查是否在目標頻道內
    if message.channel.id in REACTION_CHANNELS:
        try:
            await message.add_reaction("❤️")
        except discord.Forbidden:
            print(f"權限不足：無法在頻道 {message.channel.id} 添加反應")
        except Exception as e:
            print(f"添加反應時發生錯誤: {e}")

    # 因為你用了 bot.command，若要讓斜線指令正常運作，
    # 必須在最後面加上這行，否則其他指令會失效
    await bot.process_commands(message)

# 在 on_ready 啟動這個任務
@bot.event
async def on_ready():
    print("機器人已啟動，正在同步指令...")
    # 將這行改成這樣，可以讓你看到指令是否同步成功
    synced = await bot.tree.sync()
    print(f"已同步 {len(synced)} 個斜線指令: {[cmd.name for cmd in synced]}")
    
    bot.add_view(RoleSetupView())
    print("身分組按鈕視圖已加載。")
    
    # 啟動統計更新任務
    update_stats_channels.start()
    
    check_my_status.start()
    update_time_channel.start()
    keep_music_on_bottom.start()  # 啟動底部檢測任務

if __name__ == "__main__":
    # 啟動 Web Server 線程
    threading.Thread(target=run_web).start()
    bot.run(TOKEN)
