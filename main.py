import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from datetime import datetime, timedelta

TOKEN = os.environ.get("DISCORD_TOKEN")

# 機器人基礎設置
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 抽獎資料儲存
giveaways = {} 

# --- 抽獎互動介面 ---
class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="參加抽獎！", style=discord.ButtonStyle.green, custom_id="join_giveaway")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        if msg_id not in giveaways:
            return await interaction.response.send_message("❌ 抽獎活動已結束或不存在。", ephemeral=True)
        
        # 避免重複參加
        if interaction.user.id in giveaways[msg_id]["participants"]:
            return await interaction.response.send_message("⚠️ 你已經參加過了！", ephemeral=True)
        
        giveaways[msg_id]["participants"].add(interaction.user.id)
        await interaction.response.send_message(f"✅ 報名成功！目前累計參加人數：{len(giveaways[msg_id]['participants'])} 人。", ephemeral=True)

# --- 指令區 ---
@bot.event
async def on_ready():
    print(f"機器人已啟動：{bot.user}")
    synced = await bot.tree.sync()
    print(f"已同步 {len(synced)} 個指令")

@bot.tree.command(name="giveaway", description="[管理員] 建立抽獎活動 (輸入時、分、秒)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    prize="請輸入要抽取的獎品名稱",
    hours="輸入小時數",
    minutes="輸入分鐘數",
    seconds="輸入秒數"
)
async def create_giveaway(
    interaction: discord.Interaction, 
    prize: str, 
    hours: int = 0, 
    minutes: int = 0, 
    seconds: int = 0
):
    # 計算總時長
    total_seconds = hours * 3600 + minutes * 60 + seconds
    if total_seconds <= 0:
        return await interaction.response.send_message("❌ 時間設置錯誤，請至少輸入 1 秒。", ephemeral=True)
    
    end_time = datetime.now() + timedelta(seconds=total_seconds)
    
    embed = discord.Embed(
        title="🎁 舉辦抽獎活動",
        description=f"獎品內容：**{prize}**\n截止時間：{end_time.strftime('%Y-%m-%d %H:%M:%S')}",
        color=discord.Color.gold()
    )
    embed.set_footer(text="點擊下方按鈕即可參加！")
    
    msg = await interaction.channel.send(embed=embed, view=GiveawayView())
    giveaways[str(msg.id)] = {"prize": prize, "participants": set()}
    
    await interaction.response.send_message(f"✅ 抽獎活動已成功建立！(活動 ID: {msg.id})", ephemeral=True)

@bot.tree.command(name="draw", description="[管理員] 結算抽獎結果")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(message_id="請輸入抽獎訊息的 ID")
async def draw_giveaway(interaction: discord.Interaction, message_id: str):
    data = giveaways.get(message_id)
    if not data:
        return await interaction.response.send_message("❌ 找不到該 ID 的抽獎活動。", ephemeral=True)

    # 結算結果 (動過手腳邏輯)
    embed = discord.Embed(title="📢 抽獎結果揭曉", color=discord.Color.red())
    embed.add_field(name="獎品", value=data['prize'], inline=False)
    embed.add_field(name="得獎者", value="本次抽獎無人獲獎，感謝大家的參與！", inline=False)
    
    await interaction.channel.send(embed=embed)
    
    # 清理資料
    del giveaways[message_id]
    await interaction.response.send_message("✅ 抽獎已結算完成。", ephemeral=True)

bot.run(TOKEN)
