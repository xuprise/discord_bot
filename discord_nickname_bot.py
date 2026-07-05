"""
Discord 暱稱監控 Bot
功能：監控特定身份組的成員，若暱稱不符合設定，自動改回來
"""

import discord
from discord.ext import commands
import json
import os

# ============================================================
#  ⚙️  設定區（你只需要修改這裡）
# ============================================================

BOT_TOKEN = os.environ.get("DISCORD_TOKEN")

# 要強制執行的暱稱規則
# 格式：{ 用戶ID(字串): "強制暱稱" }
# 範例：{ "123456789012345678": "小明", "987654321098765432": "阿花" }
NICKNAME_RULES: dict[str, str] = {
    "459364281448923166": "全糖死太監",
    "679659112791146658": "腎虧陽痿狗亦宏",
    "557497112783355904": "下體爛掉狗亦宏",
}

# 只對哪些身份組套用規則
# 格式：[身份組ID(整數), ...]
# 留空 [] = 對所有人套用（只要在 NICKNAME_RULES 裡有設定）
TARGET_ROLE_IDS: list[int] = [
    # 範例：123456789012345678
]

# 記錄 log 的頻道 ID（填 0 表示不記錄）
LOG_CHANNEL_ID: int = 0

# ============================================================

intents = discord.Intents.default()
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def send_log(guild: discord.Guild, message: str):
    """傳送 log 到指定頻道"""
    if LOG_CHANNEL_ID:
        ch = guild.get_channel(LOG_CHANNEL_ID)
        if ch:
            await ch.send(f"📋 {message}")


async def enforce_nickname(member: discord.Member):
    """檢查並強制套用暱稱"""
    user_id = str(member.id)

    # 不在規則名單內 → 略過
    if user_id not in NICKNAME_RULES:
        return

    # 有設定身份組限制 → 檢查成員是否有其中一個身份組
    if TARGET_ROLE_IDS:
        member_role_ids = {r.id for r in member.roles}
        if not member_role_ids.intersection(TARGET_ROLE_IDS):
            return

    target_nick = NICKNAME_RULES[user_id]
    current_nick = member.nick or member.name

    # 暱稱已正確 → 不動
    if current_nick == target_nick:
        return

    try:
        await member.edit(nick=target_nick, reason="暱稱監控 Bot 自動糾正")
        msg = (
            f"✅ 已將 {member.name}（ID: {member.id}）的暱稱"
            f" 從「{current_nick}」改為「{target_nick}」"
        )
        print(msg)
        await send_log(member.guild, msg)
    except discord.Forbidden:
        print(f"⚠️  沒有權限修改 {member.name} 的暱稱（對方身份組可能比 Bot 高）")
    except discord.HTTPException as e:
        print(f"❌ 修改暱稱失敗：{e}")


@bot.event
async def on_ready():
    print(f"✅ Bot 已上線：{bot.user}（ID: {bot.user.id}）")
    print(f"📌 監控中的用戶數：{len(NICKNAME_RULES)}")

    # 啟動時掃描所有伺服器，立即糾正不符合的暱稱
    for guild in bot.guilds:
        print(f"🔍 掃描伺服器：{guild.name}")
        for member in guild.members:
            await enforce_nickname(member)
    print("✅ 初始掃描完成")


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """成員資料更新時觸發（包含改名）"""
    if before.nick != after.nick:
        await enforce_nickname(after)


@bot.event
async def on_member_join(member: discord.Member):
    """新成員加入時觸發"""
    await enforce_nickname(member)


# ============================================================
#  管理指令（只有管理員可用）
# ============================================================

@bot.command(name="set_nick")
@commands.has_permissions(manage_nicknames=True)
async def set_nick(ctx, user: discord.Member, *, nickname: str):
    """
    指令：!set_nick @用戶 新暱稱
    動態加入規則並立即套用
    """
    NICKNAME_RULES[str(user.id)] = nickname
    await enforce_nickname(user)
    await ctx.send(f"✅ 已將 {user.name} 的強制暱稱設為「{nickname}」")


@bot.command(name="remove_nick")
@commands.has_permissions(manage_nicknames=True)
async def remove_nick(ctx, user: discord.Member):
    """
    指令：!remove_nick @用戶
    移除該用戶的暱稱強制規則
    """
    uid = str(user.id)
    if uid in NICKNAME_RULES:
        del NICKNAME_RULES[uid]
        await ctx.send(f"✅ 已移除 {user.name} 的暱稱規則")
    else:
        await ctx.send(f"⚠️  {user.name} 沒有設定規則")


@bot.command(name="list_nicks")
@commands.has_permissions(manage_nicknames=True)
async def list_nicks(ctx):
    """
    指令：!list_nicks
    列出所有強制暱稱規則
    """
    if not NICKNAME_RULES:
        await ctx.send("目前沒有設定任何規則")
        return
    lines = ["**目前的暱稱規則：**"]
    for uid, nick in NICKNAME_RULES.items():
        member = ctx.guild.get_member(int(uid))
        name = member.name if member else f"（用戶 ID: {uid}）"
        lines.append(f"• {name} → `{nick}`")
    await ctx.send("\n".join(lines))


@bot.command(name="scan")
@commands.has_permissions(manage_nicknames=True)
async def scan(ctx):
    """
    指令：!scan
    手動觸發全伺服器掃描
    """
    await ctx.send("🔍 開始掃描...")
    count = 0
    for member in ctx.guild.members:
        uid = str(member.id)
        if uid in NICKNAME_RULES:
            before = member.nick or member.name
            await enforce_nickname(member)
            after_member = ctx.guild.get_member(member.id)
            if after_member and (after_member.nick or after_member.name) != before:
                count += 1
    await ctx.send(f"✅ 掃描完成，共糾正了 {count} 個暱稱")


bot.run(BOT_TOKEN)
