import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from datetime import datetime, timedelta

TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 儲存抽獎資料 {msg_id: {"prize": str, "end_time": datetime, "participants": set()}}
giveaways = {} 

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="參加抽獎！", style=discord.ButtonStyle.green, custom_id="join_giveaway")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        if msg_id not in giveaways:
            return await interaction.response.send_message("❌ 抽獎已結束。", ephemeral=True)
        
        if interaction.user.id in giveaways[msg_id]["participants"]:
            return await interaction.response.send_message("⚠️ 你已經參加過了。", ephemeral=True)
        
        giveaways[msg_id]["participants"].add(interaction.user.id)
        await interaction.response.send_message(f"✅ 報名成功！", ephemeral=True)

@tasks.loop(seconds=10)
async def update_giveaway_timers():
    for msg_id, data in list(giveaways.items()):
        remaining = data["end_time"] - datetime.now()
        if remaining.total_seconds() <= 0:
            continue # 等待結算指令
        
        # 格式化剩餘時間
        mins, secs = divmod(int(remaining.total_seconds()), 60)
        hours, mins = divmod(mins, 60)
        time_str = f"{hours}時 {mins}分 {secs}秒"
        
        try:
            channel = bot.get_channel(data["channel_id"])
            msg = await channel.fetch_message(int(msg_id))
            new_embed = msg.embeds[0]
            new_embed.description = f"獎品內容：**{data['prize']}**\n剩餘時間：**{time_str}**"
            await msg.edit(embed=new_embed)
        except: continue

@bot.event
async def on_ready():
    update_giveaway_timers.start()
    await bot.tree.sync()
    print("機器人已啟動，倒數計時器已啟動。")

@bot.tree.command(name="giveaway", description="[管理員] 建立抽獎活動")
@app_commands.checks.has_permissions(administrator=True)
async def create_giveaway(interaction: discord.Interaction, prize: str, hours: int = 0, minutes: int = 0, seconds: int = 0):
    total_seconds = hours * 3600 + minutes * 60 + seconds
    end_time = datetime.now() + timedelta(seconds=total_seconds)
    
    embed = discord.Embed(
        title="🎁 抽獎活動",
        description=f"獎品內容：**{prize}**\n剩餘時間：**{hours}時 {minutes}分 {seconds}秒**",
        color=discord.Color.gold()
    )
    
    msg = await interaction.channel.send(embed=embed, view=GiveawayView())
    giveaways[str(msg.id)] = {
        "prize": prize, 
        "end_time": end_time, 
        "participants": set(), 
        "channel_id": interaction.channel.id
    }
    await interaction.response.send_message(f"✅ 抽獎已建立！ID: {msg.id}", ephemeral=True)

@bot.tree.command(name="draw", description="[管理員] 結算抽獎")
@app_commands.checks.has_permissions(administrator=True)
async def draw_giveaway(interaction: discord.Interaction, message_id: str):
    if message_id not in giveaways:
        return await interaction.response.send_message("❌ 找不到該抽獎 ID。", ephemeral=True)
    
    data = giveaways[message_id]
    embed = discord.Embed(title="📢 抽獎結果揭曉", color=discord.Color.red())
    embed.add_field(name="獎品", value=data['prize'], inline=False)
    embed.add_field(name="得獎者", value="本次抽獎無人獲獎，感謝參與！", inline=False)
    
    await interaction.channel.send(embed=embed)
    del giveaways[message_id]
    await interaction.response.send_message("✅ 結算完成。", ephemeral=True)

bot.run(TOKEN)
