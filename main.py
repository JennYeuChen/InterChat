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

# --- 🔰 全新等級系統 (斜線指令版) ---
LEVEL_DATA_FILE = os.path.join(DATA_FOLDER, "user_levels.json")

# 載入等級資料
def load_level_data():
    if os.path.exists(LEVEL_DATA_FILE):
        with open(LEVEL_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

user_levels = load_level_data()

def save_level_data():
    with open(LEVEL_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(user_levels, f, indent=4, ensure_ascii=False)

# 修改等級邏輯：直接以總訊息量決定等級
def get_level_info(total_msg):
    # 每 50 則訊息升一級
    return (total_msg // 50) + 1

# 修改 add_exp_on_message (改名為 track_activity)
async def track_activity(message):
    uid = str(message.author.id)
    today = datetime.now().strftime("%Y-%m-%d")

    if uid not in user_levels:
        user_levels[uid] = {"total_msg": 0, "daily_msg": 0, "last_date": today}
    
    # 每日重置
    if user_levels[uid].get("last_date") != today:
        user_levels[uid]["daily_msg"] = 0
        user_levels[uid]["last_date"] = today
    
    user_levels[uid]["total_msg"] += 1
    user_levels[uid]["daily_msg"] += 1
    
    # 檢查升級 (不需要紀錄 exp 了)
    new_level = get_level_info(user_levels[uid]["total_msg"])
    old_level = get_level_info(user_levels[uid]["total_msg"] - 1)
    
    if new_level > old_level:
        await message.channel.send(f"🎉 恭喜 {message.author.mention} 升級至 **Lv.{new_level}**！")
    
    save_level_data()

# --- 斜線指令：查詢等級 ---
@bot.tree.command(name="level", description="查詢指定用戶的等級與發言狀況")
@app_commands.describe(member="要查詢的對象（預設為自己）")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    uid = str(target.id)
    data = user_levels.get(uid, {"total_msg": 0, "daily_msg": 0})
    
    level = get_level_info(data["total_msg"])
    progress = (data["total_msg"] % 50) // 5 # 每 5 則訊息顯示一個綠點
    bar = "🟢" * progress + "🔴" * (10 - progress)
    
    embed = discord.Embed(title=f"📊 {target.display_name} 的活躍面板", color=discord.Color.green())
    embed.add_field(name="等級進度", value=f"Lv.{level}\n{bar}", inline=False)
    embed.add_field(name="今日發言", value=f"`{data.get('daily_msg', 0)}` 則", inline=True)
    embed.add_field(name="累計發言", value=f"`{data.get('total_msg', 0)}` 則", inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=False)

# --- 斜線指令：查詢伺服器今日總發言量 ---
@bot.tree.command(name="server_stats", description="查詢伺服器今日總發言量")
async def server_stats(interaction: discord.Interaction):
    total_today = sum(user.get("daily_msg", 0) for user in user_levels.values())
    
    embed = discord.Embed(title="📈 伺服器今日戰報", color=discord.Color.gold())
    embed.description = f"今日全體成員共發送了 **{total_today}** 則訊息！"
    await interaction.response.send_message(embed=embed, ephemeral=False)

# --- 斜線指令：重置所有人的經驗 (管理員專用) ---
@bot.tree.command(name="reset_levels", description="[管理員] 重置所有用戶的等級與經驗值")
@app_commands.checks.has_permissions(administrator=True)
async def reset_all_levels(interaction: discord.Interaction):
    global user_levels
    user_levels = {}
    save_level_data()
    await interaction.response.send_message("✅ 已成功重置所有人的等級資料庫。", ephemeral=True)

# --- 斜線指令：重置今日統計 (管理員專用) ---
@bot.tree.command(name="reset_daily", description="[管理員] 重置所有人的今日發言統計")
@app_commands.checks.has_permissions(administrator=True)
async def reset_daily(interaction: discord.Interaction):
    today = datetime.now().strftime("%Y-%m-%d")
    for uid in user_levels:
        user_levels[uid]["daily_msg"] = 0
        user_levels[uid]["last_date"] = today
    save_level_data()
    await interaction.response.send_message("✅ 今日發言統計已歸零。", ephemeral=False)

@bot.event
async def on_message(message):
    # 1. 處理指定頻道的「自動表情反應」
    if message.channel.id in REACTION_CHANNELS and not message.author.bot:
        try:
            # 使用 await asyncio.gather 讓反應速度更快，不用一個一個等
            await asyncio.gather(
                message.add_reaction("❤️"),
                message.add_reaction("🗑️")
            )
        except discord.Forbidden:
            print(f"機器人沒有在頻道 {message.channel.id} 新增反應的權限")
        except discord.HTTPException:
            pass

    # 1.5. 等級系統處理 (只要不是機器人說的話都會加經驗)
    if not message.author.bot:
        await track_activity(message)

    # 2. 原有的 CrossChat 邏輯
    if message.author.bot or message.channel.id not in CROSS_CHAT_CHANNELS:
        await bot.process_commands(message)
        return

    # 針對目標頻道發送訊息 (保留原有的 CrossChat 邏輯)
    for channel_id in CROSS_CHAT_CHANNELS:
        if channel_id != message.channel.id:
            target_channel = bot.get_channel(channel_id)
            if target_channel:
                webhooks = await target_channel.webhooks()
                webhook = next((w for w in webhooks if w.name == "CrossChat"), None)
                if not webhook:
                    webhook = await target_channel.create_webhook(name="CrossChat")
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
current_music_msg_id = None  # 音樂頻道中那則訊息的 ID
current_active_theme = None   # 當前被選中的主題文字
# 定義需要自動加入反應的頻道列表
REACTION_CHANNELS = [1524036557948977152, 1508029438972137552]
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

# 在 on_ready 啟動這個任務
@bot.event
async def on_ready():
    print("機器人已啟動...")
    await bot.tree.sync()
    check_my_status.start()
    update_time_channel.start()
    keep_music_on_bottom.start()  # 啟動底部檢測任務

if __name__ == "__main__":
    # 啟動 Web Server 線程
    threading.Thread(target=run_web).start()
    bot.run(TOKEN)
