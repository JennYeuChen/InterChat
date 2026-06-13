import discord
from discord.ext import commands

# 1. 設定你的 Discord 機器人 Token
TOKEN = '你的_BOT_TOKEN_在這裡'

# 2. 設定參與跨群聊天的頻道 ID (將所有伺服器中要進行聊天的頻道 ID 填入)
CROSS_CHAT_CHANNELS = [
    123456789012345678, # 伺服器 A 的頻道 ID
    876543210987654321, # 伺服器 B 的頻道 ID
]

intents = discord.Intents.default()
intents.message_content = True  # 必須開啟此權限才能讀取訊息內容
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'✅ 跨群聊天機器人已啟動，帳號: {bot.user}')

@bot.event
async def on_message(message):
    # 避免機器人處理自己的訊息或非跨群頻道的訊息
    if message.author.bot or message.channel.id not in CROSS_CHAT_CHANNELS:
        await bot.process_commands(message)
        return

    # 轉發訊息到其他群組
    for channel_id in CROSS_CHAT_CHANNELS:
        if channel_id != message.channel.id:  # 不要回傳給自己
            target_channel = bot.get_channel(channel_id)
            if target_channel:
                # 建立專業的 Embed 格式
                embed = discord.Embed(
                    description=message.content,
                    color=discord.Color.green()
                )
                # 顯示發送者名稱與伺服器名稱
                embed.set_author(
                    name=f"{message.author.display_name} @ {message.guild.name}",
                    icon_url=message.author.avatar.url if message.author.avatar else None
                )
                
                # 處理圖片轉發
                if message.attachments:
                    embed.set_image(url=message.attachments[0].url)

                await target_channel.send(embed=embed)
    
    await bot.process_commands(message)

bot.run(TOKEN)
