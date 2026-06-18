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
intents.members = True
intents.voice_states = True
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

@bot.event
async def on_voice_state_update(member, before, after):
    # --- 原有的你自己的監測邏輯 ---
    if member.id == MY_ID:
        projection_channel = bot.get_channel(PROJECTION_CHANNEL_ID)
        if not projection_channel:
            return
        
        # 進入柏仔群
        if after.channel and after.channel.id in TARGET_VOICE_CHANNELS:
            count = len(after.channel.members)
            await projection_channel.edit(name=f"🔴｜瑪芬和{count}個仁在柏仔群裡")
            # 機器人加入語音 (保持原本的連接邏輯)
            if BOT_JOIN_CHANNEL_ID:
                bot_join_channel = bot.get_channel(BOT_JOIN_CHANNEL_ID)
                if bot_join_channel and not bot.voice_clients:
                    await bot_join_channel.connect()
            
        # 離開柏仔群
        elif before.channel and before.channel.id in TARGET_VOICE_CHANNELS and (not after.channel or after.channel.id not in TARGET_VOICE_CHANNELS):
            await projection_channel.edit(name="🟢｜瑪芬在群裡")
            # 機器人斷開 (保持原本的斷開邏輯)
            for vc in bot.voice_clients:
                await vc.disconnect()

    # --- 新增：監測頻道人數變動 (即時投影) ---
    # 檢查是否有其他人進出你所在的同一個頻道
    target_channel_id = after.channel.id if after.channel else before.channel.id
    target_channel = bot.get_channel(target_channel_id)
    if target_channel and target_channel.id in TARGET_VOICE_CHANNELS:
        # 檢查你自己是否還在裡面
        you = target_channel.guild.get_member(MY_ID)
        if you and you.voice and you.voice.channel and you.voice.channel.id == target_channel.id:
            count = len(target_channel.members)
            projection_channel = bot.get_channel(PROJECTION_CHANNEL_ID)
            if projection_channel:
                await projection_channel.edit(name=f"🔴｜瑪芬和{count}個仁在柏仔群裡")

if __name__ == "__main__":
    # 啟動 Web Server 線程
    threading.Thread(target=run_web).start()
    bot.run(TOKEN)
