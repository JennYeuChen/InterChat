import discord
from discord.ext import commands, tasks
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

@bot.event
async def on_voice_state_update(member, before, after):
    # 只監控你自己
    if member.id != MY_ID:
        return

    projection_channel = bot.get_channel(PROJECTION_CHANNEL_ID)
    if not projection_channel:
        return

    # 只要你進入任何語音房，就觸發
    if after.channel is not None:
        # 這裡不監測具體在哪個群，而是直接顯示你在語音
        await projection_channel.edit(name="🔴｜瑪芬正在柏仔群")
    # 如果你離開語音房
    elif after.channel is None:
        await projection_channel.edit(name="🟢｜瑪芬在群裡")

@bot.event
async def on_ready():
    print(f'機器人已上線: {bot.user}')

if __name__ == "__main__":
    # 啟動 Web Server 線程
    threading.Thread(target=run_web).start()
    bot.run(TOKEN)
