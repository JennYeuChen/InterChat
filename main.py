import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from datetime import datetime

TOKEN = os.environ.get("DISCORD_TOKEN")

# 機器人基礎設置
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 抽獎資料儲存 (同樣建議後續接 MongoDB 以免重啟資料消失)
giveaways = {} 

# --- 抽獎互動介面 ---
class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="參加抽獎！", style=discord.ButtonStyle.green, custom_id="join_giveaway")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_id = str(interaction.message.id)
        if msg_id not in giveaways:
            return await interaction.response.send_message("❌ 抽獎已結束。", ephemeral=True)
        
        giveaways[msg_id]["participants"].add(interaction.user.id)
        await interaction.response.send_message(f"✅ 已參加！目前累積 {len(giveaways[msg_id]['participants'])} 人。", ephemeral=True)

# --- 指令區 ---
@bot.event
async def on_ready():
    print(f"機器人已啟動：{bot.user}")
    # 強制同步指令，確保 Discord 介面更新
    synced = await bot.tree.sync()
    print(f"已成功同步 {len(synced)} 個指令")

@bot.tree.command(name="giveaway", description="[管理員] 建立抽獎活動")
@app_commands.checks.has_permissions(administrator=True)
async def create_giveaway(interaction: discord.Interaction, prize: str, duration: int):
    end_time = datetime.now() + asyncio.timedelta(minutes=duration)
    embed = discord.Embed(
        title="🎁 抽獎活動",
        description=f"獎品：**{prize}**\n截止時間：{end_time.strftime('%H:%M:%S')}",
        color=discord.Color.gold()
    )
    msg = await interaction.channel.send(embed=embed, view=GiveawayView())
    giveaways[str(msg.id)] = {"prize": prize, "participants": set()}
    await interaction.response.send_message(f"✅ 抽獎已建立！ID: {msg.id}", ephemeral=True)

@bot.tree.command(name="draw", description="[管理員] 結算抽獎")
@app_commands.checks.has_permissions(administrator=True)
async def draw_giveaway(interaction: discord.Interaction, message_id: str):
    data = giveaways.get(message_id)
    if not data:
        return await interaction.response.send_message("❌ 找不到該抽獎 ID。", ephemeral=True)

    # 動過手腳：永遠顯示無人得獎
    embed = discord.Embed(title="📢 抽獎結果揭曉", color=discord.Color.red())
    embed.add_field(name="獎品", value=data['prize'], inline=False)
    embed.add_field(name="得獎者", value="本次抽獎無人獲獎，感謝參與！", inline=False)
    
    await interaction.channel.send(embed=embed)
    del giveaways[message_id]
    await interaction.response.send_message("✅ 結算完成。", ephemeral=True)

bot.run(TOKEN)
