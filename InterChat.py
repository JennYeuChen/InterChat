import discord
from discord.ext import commands
import os

# 從環境變數讀取 Token (雲端平台設定)
TOKEN = os.environ.get("DISCORD_TOKEN")

# 設定參與聊天的頻道 ID (可使用環境變數或直接寫入)
# 如果頻道很多，建議之後改用 JSON 檔案存儲
CROSS_CHAT_CHANNELS = [
    int(cid) for cid in os.environ.get("CROSS_CHAT_CHANNELS", "").split(",") if cid
]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ 跨群聊天系統啟動成功: {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot or message.channel.id not in CROSS_CHAT_CHANNELS:
        await bot.process_commands(message)
        return

    # 轉發邏輯
    for channel_id in CROSS_CHAT_CHANNELS:
        if channel_id != message.channel.id:
            target_channel = bot.get_channel(channel_id)
            if target_channel:
                embed = discord.Embed(description=message.content, color=discord.Color.green())
                embed.set_author(
                    name=f"{message.author.display_name} @ {message.guild.name}",
                    icon_url=message.author.avatar.url if message.author.avatar else None
                )
                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)
                await target_channel.send(embed=embed)
    
    await bot.process_commands(message)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ 錯誤：請在環境變數中設定 DISCORD_TOKEN")
    else:
        bot.run(TOKEN)
