import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from datetime import datetime, timedelta

# 機器人 Token
TOKEN = os.environ.get("DISCORD_TOKEN")

# 機器人基礎設置
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 抽獎資料儲存 (記憶體模式)
giveaways = {} 

# --- 抽獎互動按鈕邏輯 ---
class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="參加抽獎！", style=discord.ButtonStyle.green, custom_id="join_giveaway")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        if msg_id not in giveaways:
            return await interaction.response.send_message("❌ 抽獎活動已結束或不存在。", ephemeral=True)
        
        if interaction.user.id in giveaways[msg_id]["participants"]:
            return await interaction.response.send_message("⚠️ 你已經參加過了。", ephemeral=True)
        
        giveaways[msg_id]["participants"].add(interaction.user.id)
        await interaction.response.send_message(f"✅ 報名成功！目前累計人數：{len(giveaways[msg_id]['participants'])} 人。", ephemeral=True)

# --- 定時更新倒數任務 ---
@tasks.loop(seconds=10)
async def update_giveaway_timers():
    for msg_id, data in list(giveaways.items()):
        remaining = data["end_time"] - datetime.now()
        if remaining.total_seconds() <= 0:
            continue
        
        total_secs = int(remaining.total_seconds())
        days, rem = divmod(total_secs, 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        
        time_str = f"{days}天 {hours}時 {mins}分 {secs}秒"
        
        try:
            channel = bot.get_channel(data["channel_id"])
            msg = await channel.fetch_message(int(msg_id))
            new_embed = msg.embeds[0]
            new_embed.description = f"獎品內容：**{data['prize']}**\n剩餘時間：**{time_str}**"
            await msg.edit(embed=new_embed)
        except: continue

# --- 機器人事件 ---
@bot.event
async def on_ready():
    print(f"機器人已啟動：{bot.user}")
    update_giveaway_timers.start()
    synced = await bot.tree.sync()
    print(f"已成功同步 {len(synced)} 個指令")

# --- 指令區 ---
@bot.tree.command(name="giveaway", description="[管理員] 建立抽獎活動 (輸入天時分秒)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(prize="獎品名稱", days="天數", hours="小時", minutes="分鐘", seconds="秒數")
async def create_giveaway(interaction: discord.Interaction, prize: str, days: int = 0, hours: int = 0, minutes: int = 0, seconds: int = 0):
    total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60) + seconds
    if total_seconds <= 0:
        return await interaction.response.send_message("❌ 時間設置錯誤，請至少輸入 1 秒。", ephemeral=True)
    
    end_time = datetime.now() + timedelta(seconds=total_seconds)
    
    embed = discord.Embed(
        title="🎁 舉辦抽獎活動",
        description=f"獎品內容：**{prize}**\n剩餘時間：**{days}天 {hours}時 {minutes}分 {seconds}秒**",
        color=discord.Color.gold()
    )
    
    msg = await interaction.channel.send(embed=embed, view=GiveawayView())
    giveaways[str(msg.id)] = {
        "prize": prize, 
        "end_time": end_time, 
        "participants": set(), 
        "channel_id": interaction.channel.id
    }
    await interaction.response.send_message(f"✅ 抽獎活動已成功建立！(活動 ID: {msg.id})", ephemeral=True)

@bot.tree.command(name="draw", description="[管理員] 結算抽獎")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message_id="請輸入抽獎訊息 ID")
async def draw_giveaway(interaction: discord.Interaction, message_id: str):
    data = giveaways.get(message_id)
    if not data:
        return await interaction.response.send_message("❌ 找不到該抽獎 ID。", ephemeral=True)

    # 動過手腳：永遠無人得獎
    embed = discord.Embed(title="📢 抽獎結果揭曉", color=discord.Color.red())
    embed.add_field(name="獎品", value=data['prize'], inline=False)
    embed.add_field(name="得獎者", value="本次抽獎無人獲獎，感謝大家的參與！", inline=False)
    
    await interaction.channel.send(embed=embed)
    del giveaways[message_id]
    await interaction.response.send_message("✅ 結算完成。", ephemeral=True)

bot.run(TOKEN)
