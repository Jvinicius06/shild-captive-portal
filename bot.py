import json
import logging
import re
import secrets
import time

import discord
from discord import app_commands

import config
import firewall

log = logging.getLogger(__name__)

CODE_PATTERN = re.compile(r"^[A-Z0-9]{4}$")

_redis = None


def init(redis_client):
    global _redis
    _redis = redis_client


intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


def _log_webhook(title: str, description: str, color: int = 0x00FF00):
    """Send a log embed to the configured webhook, if any."""
    if not config.LOG_WEBHOOK:
        return
    import urllib.request

    payload = json.dumps({
        "embeds": [{
            "title": title,
            "description": description,
            "color": color,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }]
    })
    req = urllib.request.Request(
        config.LOG_WEBHOOK,
        data=payload.encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        log.warning("Failed to send log webhook: %s", e)


@client.event
async def on_ready():
    log.info("Discord bot logged in as %s", client.user)
    if config.DISCORD_GUILD_ID:
        guild = discord.Object(id=config.DISCORD_GUILD_ID)
        tree.copy_global_to(guild=guild)
        await tree.sync(guild=guild)
    else:
        await tree.sync()
    log.info("Slash commands synced")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id != config.DISCORD_CHANNEL_ID:
        return

    text = message.content.strip().upper()

    if not CODE_PATTERN.match(text):
        return

    code = text
    key = f"whitelist:code:{code}"
    raw = _redis.get(key)

    if raw is None:
        embed = discord.Embed(
            title="Codigo invalido",
            description="Codigo invalido ou expirado. Gere um novo no portal.",
            color=0xFF0000,
        )
        await message.reply(embed=embed)
        return

    data = json.loads(raw)
    ip = data["ip"]

    success = firewall.add_ip(ip)

    if not success:
        embed = discord.Embed(
            title="Erro",
            description="Falha ao liberar o IP. Contate um administrador.",
            color=0xFF0000,
        )
        await message.reply(embed=embed)
        return

    _redis.delete(key)

    active_data = json.dumps({
        "discord_id": str(message.author.id),
        "discord_name": str(message.author),
        "timestamp": time.time(),
    })
    _redis.set(f"whitelist:active:{ip}", active_data)

    # Create a session token for auto-renewal (cookie-based)
    session_token = secrets.token_hex(32)
    session_data = json.dumps({
        "discord_id": str(message.author.id),
        "discord_name": str(message.author),
        "ip": ip,
        "created_at": time.time(),
    })
    _redis.setex(f"whitelist:session:{session_token}", config.SESSION_TTL, session_data)
    # Store pending cookie so the web server can set it on next page load
    _redis.setex(f"whitelist:pending_session:{ip}", config.CODE_TTL, session_token)

    embed = discord.Embed(
        title="IP Liberado!",
        description=f"Seu IP foi liberado com sucesso.\nVoce ja pode conectar no servidor FiveM.\n\nCaso nao consiga acessar a cidade, entre no portal: {config.PORTAL_URL}",
        color=0x00FF00,
    )
    embed.set_footer(text=f"Liberado por {message.author}")
    await message.reply(embed=embed)

    _log_webhook(
        "IP Liberado",
        f"**IP:** `{ip}`\n**Discord:** {message.author} ({message.author.id})",
    )

    log.info("IP %s whitelisted by %s (%s)", ip, message.author, message.author.id)


def _is_admin(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    return False


whitelist_group = app_commands.Group(name="whitelist", description="Gerenciar whitelist de IPs")


@whitelist_group.command(name="list", description="Listar IPs liberados")
async def whitelist_list(interaction: discord.Interaction):
    if not _is_admin(interaction):
        await interaction.response.send_message("Sem permissao.", ephemeral=True)
        return

    ips = firewall.list_ips()

    if not ips:
        await interaction.response.send_message("Nenhum IP na whitelist.", ephemeral=True)
        return

    lines = []
    for ip in ips:
        raw = _redis.get(f"whitelist:active:{ip}")
        if raw:
            info = json.loads(raw)
            lines.append(f"`{ip}` - {info.get('discord_name', '?')}")
        else:
            lines.append(f"`{ip}` - (sem info)")

    description = "\n".join(lines)
    if len(description) > 4000:
        description = description[:4000] + "\n..."

    embed = discord.Embed(
        title=f"Whitelist ({len(ips)} IPs)",
        description=description,
        color=0x3498DB,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@whitelist_group.command(name="remove", description="Remover um IP da whitelist")
@app_commands.describe(ip="IP para remover")
async def whitelist_remove(interaction: discord.Interaction, ip: str):
    if not _is_admin(interaction):
        await interaction.response.send_message("Sem permissao.", ephemeral=True)
        return

    success = firewall.remove_ip(ip)
    if success:
        _redis.delete(f"whitelist:active:{ip}")
        await interaction.response.send_message(f"IP `{ip}` removido.", ephemeral=True)
        _log_webhook("IP Removido", f"**IP:** `{ip}`\n**Por:** {interaction.user}", color=0xFF9900)
    else:
        await interaction.response.send_message(f"Falha ao remover `{ip}`.", ephemeral=True)


@whitelist_group.command(name="flush", description="Limpar todos os IPs da whitelist")
async def whitelist_flush(interaction: discord.Interaction):
    if not _is_admin(interaction):
        await interaction.response.send_message("Sem permissao.", ephemeral=True)
        return

    success = firewall.flush()
    if success:
        for key in _redis.scan_iter("whitelist:active:*"):
            _redis.delete(key)
        await interaction.response.send_message("Whitelist limpa.", ephemeral=True)
        _log_webhook("Whitelist Limpa", f"**Por:** {interaction.user}", color=0xFF0000)
    else:
        await interaction.response.send_message("Falha ao limpar whitelist.", ephemeral=True)


tree.add_command(whitelist_group)
