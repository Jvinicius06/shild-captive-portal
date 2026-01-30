#!/usr/bin/env python3
"""
Elysius Shield Client - Windows System Tray Application

Faz todo o processo de whitelist automaticamente:
1. Gera código de 4 dígitos
2. Aguarda validação no Discord
3. Salva a sessão
4. Renova automaticamente
"""

import json
import logging
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import pystray
import requests
from PIL import Image, ImageDraw, ImageFont
from pystray import MenuItem as item

# Configuração
APP_NAME = "Elysius Shield"
CONFIG_FILE = Path(os.getenv("APPDATA", ".")) / "ElysiusShield" / "config.json"
LOG_FILE = Path(os.getenv("APPDATA", ".")) / "ElysiusShield" / "client.log"

# Valores padrão
DEFAULT_CONFIG = {
    "portal_url": "https://shield.elysiusrp.com.br",
    "refresh_interval": 60,  # segundos
    "session_token": "",
    "discord_name": "",
    "last_ip": "",
}

# Estado global
_running = True
_status = "Iniciando..."
_status_detail = ""
_last_refresh = None
_icon = None
_config = DEFAULT_CONFIG.copy()
_pending_code = None
_code_check_active = False


def setup_logging():
    """Configura o logging para arquivo e console."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger(__name__)


log = setup_logging()


def load_config():
    """Carrega configuração do arquivo ou cria padrão."""
    global _config

    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                _config = {**DEFAULT_CONFIG, **json.load(f)}
                log.info("Configuracao carregada de %s", CONFIG_FILE)
        except Exception as e:
            log.error("Erro ao carregar config: %s", e)
            _config = DEFAULT_CONFIG.copy()
    else:
        save_config()
        log.info("Arquivo de configuracao criado: %s", CONFIG_FILE)

    return _config


def save_config():
    """Salva configuração atual no arquivo."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Salvar apenas campos persistentes
        to_save = {
            "portal_url": _config.get("portal_url", DEFAULT_CONFIG["portal_url"]),
            "refresh_interval": _config.get("refresh_interval", DEFAULT_CONFIG["refresh_interval"]),
            "session_token": _config.get("session_token", ""),
            "discord_name": _config.get("discord_name", ""),
            "last_ip": _config.get("last_ip", ""),
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=2)
        log.info("Configuracao salva")
    except Exception as e:
        log.error("Erro ao salvar config: %s", e)


def create_icon_image(color="gray", text="E"):
    """Cria uma imagem para o ícone da system tray."""
    colors = {
        "green": "#22c55e",   # Conectado
        "yellow": "#eab308",  # Renovando/Aguardando
        "red": "#ef4444",     # Erro
        "gray": "#6b7280",    # Desconectado
        "blue": "#3b82f6",    # Aguardando código
    }

    # Criar imagem 64x64
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Desenhar círculo com borda
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=colors.get(color, colors["gray"]),
        outline="#1f2937",
        width=3,
    )

    # Adicionar texto no centro
    try:
        font = ImageFont.truetype("arial.ttf", 28 if len(text) > 1 else 32)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - 4
    draw.text((x, y), text, fill="white", font=font)

    return img


def update_icon_status(status: str, detail: str = "", icon_text: str = "E"):
    """Atualiza o ícone e tooltip da system tray."""
    global _status, _status_detail, _icon
    _status = status
    _status_detail = detail

    color_map = {
        "Conectado": "green",
        "Renovando...": "yellow",
        "Aguardando codigo": "blue",
        "Erro": "red",
        "Desconectado": "gray",
        "Sessao expirada": "red",
    }

    if _icon:
        _icon.icon = create_icon_image(color_map.get(status, "gray"), icon_text)
        tooltip = f"{APP_NAME} - {status}"
        if detail:
            tooltip += f"\n{detail}"
        _icon.title = tooltip


def show_notification(title: str, message: str):
    """Mostra uma notificação do sistema."""
    if _icon:
        try:
            _icon.notify(message, title)
        except Exception as e:
            log.warning("Erro ao mostrar notificacao: %s", e)


def api_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Faz uma requisição à API do portal."""
    url = _config["portal_url"].rstrip("/") + endpoint

    headers = {}
    if _config.get("session_token"):
        headers["X-Session-Token"] = _config["session_token"]

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=15)
        else:
            response = requests.post(url, headers=headers, json=data, timeout=15)

        return response.json()
    except requests.exceptions.RequestException as e:
        log.error("Erro de conexao com %s: %s", endpoint, e)
        return {"ok": False, "error": "connection", "message": str(e)}
    except json.JSONDecodeError as e:
        log.error("Resposta invalida de %s: %s", endpoint, e)
        return {"ok": False, "error": "invalid_response", "message": str(e)}


def request_code(force: bool = False) -> tuple[bool, str, str]:
    """
    Solicita um novo código de whitelist.
    Retorna: (sucesso, código ou mensagem, ip)

    Args:
        force: Se True, força geração de novo código mesmo se IP já liberado
    """
    global _pending_code

    update_icon_status("Aguardando codigo", "Solicitando...", "...")

    result = api_request("/api/request-code", "POST", {"force": force})

    if not result.get("ok"):
        error = result.get("error", "unknown")
        msg = result.get("message", "Erro desconhecido")

        if error == "rate_limit":
            return False, "Muitas tentativas. Aguarde 5 minutos.", ""

        return False, msg, ""

    # Já está liberado?
    if result.get("already_whitelisted"):
        ip = result.get("ip", "")

        # Se recebeu token, salvar
        if result.get("session_token"):
            _config["session_token"] = result["session_token"]
            _config["last_ip"] = ip
            if result.get("discord_name"):
                _config["discord_name"] = result["discord_name"]
            save_config()
            return True, "Ja liberado! Sessao criada.", ip

        # Sem token - sugerir forçar novo código
        return True, "IP liberado mas sem sessao. Clique em 'Forcar Novo Codigo'.", ip

    # Código gerado
    code = result.get("code", "")
    ip = result.get("ip", "")
    _pending_code = code

    log.info("Codigo gerado: %s para IP %s", code, ip)

    return True, code, ip


def check_code_validated() -> tuple[bool, str]:
    """
    Verifica se o código foi validado no Discord.
    Retorna: (validado, mensagem)
    """
    result = api_request("/api/check-code", "POST")

    if not result.get("ok"):
        return False, result.get("message", "Aguardando validacao...")

    if result.get("validated"):
        token = result.get("session_token")
        if token:
            _config["session_token"] = token
            save_config()
            log.info("Codigo validado! Token recebido.")
            return True, "Codigo validado! Sessao criada."

        return True, "IP liberado."

    return False, result.get("message", "Aguardando...")


def refresh_session() -> tuple[bool, str]:
    """
    Renova a sessão atual.
    Retorna: (sucesso, mensagem)
    """
    global _last_refresh

    if not _config.get("session_token"):
        return False, "Sem sessao ativa"

    update_icon_status("Renovando...", "", "...")

    result = api_request("/api/refresh-session", "POST", {
        "session_token": _config["session_token"]
    })

    if not result.get("ok"):
        error = result.get("error", "unknown")

        if error == "invalid_session":
            _config["session_token"] = ""
            save_config()
            return False, "Sessao expirada"

        return False, result.get("message", "Erro ao renovar")

    _last_refresh = datetime.now()
    ip = result.get("ip", "")
    discord_name = result.get("discord_name", "")
    ttl_days = result.get("session_ttl", 0) // 86400

    # Atualizar config
    if discord_name:
        _config["discord_name"] = discord_name
    if ip:
        _config["last_ip"] = ip
    save_config()

    if result.get("ip_changed"):
        old_ip = result.get("old_ip", "?")
        log.info("IP atualizado: %s -> %s", old_ip, ip)
        return True, f"IP atualizado para {ip} ({ttl_days}d restantes)"

    return True, f"{discord_name} | {ip} ({ttl_days}d)"


def get_session_info() -> dict:
    """Obtém informações da sessão atual."""
    if not _config.get("session_token"):
        return {"valid": False}

    result = api_request("/api/session-info", "GET")
    return result


def code_check_loop():
    """Loop que verifica se o código foi validado."""
    global _code_check_active, _pending_code

    _code_check_active = True
    attempts = 0
    max_attempts = 60  # 5 minutos (5s * 60)

    while _running and _code_check_active and _pending_code and attempts < max_attempts:
        time.sleep(5)
        attempts += 1

        validated, msg = check_code_validated()

        if validated:
            _pending_code = None
            _code_check_active = False
            update_icon_status("Conectado", msg)
            show_notification("Shield Ativado!", msg)
            log.info("Validacao concluida: %s", msg)
            return

        # Atualizar status com código
        remaining = (max_attempts - attempts) * 5
        update_icon_status(
            "Aguardando codigo",
            f"Digite {_pending_code} no Discord ({remaining}s)",
            _pending_code[:2] if _pending_code else "??"
        )

    # Timeout
    if _pending_code:
        _pending_code = None
        _code_check_active = False
        update_icon_status("Erro", "Tempo esgotado. Tente novamente.")
        show_notification("Tempo Esgotado", "O codigo expirou. Clique em 'Obter Novo Codigo'.")


def refresh_loop():
    """Loop principal que renova a sessão periodicamente."""
    global _running

    # Aguardar um pouco para o ícone carregar
    time.sleep(2)

    while _running:
        # Se tem sessão, renovar
        if _config.get("session_token"):
            success, msg = refresh_session()

            if success:
                update_icon_status("Conectado", msg)
            else:
                if "expirada" in msg.lower():
                    update_icon_status("Sessao expirada", "Clique para obter novo codigo")
                    show_notification("Sessao Expirada", "Sua sessao expirou. Obtenha um novo codigo.")
                else:
                    update_icon_status("Erro", msg)
                    log.warning("Falha na renovacao: %s", msg)

        elif not _code_check_active:
            # Sem sessão e não está aguardando código
            update_icon_status("Desconectado", "Clique para obter codigo")

        # Aguardar intervalo
        interval = _config.get("refresh_interval", 60)
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)


# ============================================================
# Ações do Menu
# ============================================================

def on_get_code(icon, item):
    """Solicita um novo código de whitelist."""
    _do_get_code(force=False)


def on_force_code(icon, item):
    """Força geração de novo código mesmo se IP já liberado."""
    _do_get_code(force=True)


def _do_get_code(force: bool = False):
    """Executa a solicitação de código."""
    def do_request():
        global _pending_code

        success, result, ip = request_code(force=force)

        if not success:
            update_icon_status("Erro", result)
            show_notification("Erro", result)
            return

        # Se já está liberado e sessão foi criada
        if "liberado" in result.lower() and "sessao" in result.lower():
            update_icon_status("Conectado", result)
            show_notification("Shield", result)
            return

        # Se precisa forçar código
        if "forcar" in result.lower():
            update_icon_status("Desconectado", result)
            show_notification("Shield", result)
            return

        # Código gerado - mostrar e iniciar verificação
        code = result
        _pending_code = code

        update_icon_status("Aguardando codigo", f"Digite {code} no Discord", code[:2])
        show_notification(
            f"Codigo: {code}",
            f"Digite {code} no canal de shield do Discord.\nSeu IP: {ip}"
        )

        # Iniciar thread de verificação
        threading.Thread(target=code_check_loop, daemon=True).start()

    threading.Thread(target=do_request, daemon=True).start()


def on_refresh_now(icon, item):
    """Força uma renovação imediata."""
    def do_refresh():
        success, msg = refresh_session()
        if success:
            update_icon_status("Conectado", msg)
            show_notification("Renovado", msg)
        else:
            update_icon_status("Erro", msg)
            show_notification("Erro", msg)

    threading.Thread(target=do_refresh, daemon=True).start()


def on_check_status(icon, item):
    """Verifica o status atual."""
    def do_check():
        info = get_session_info()

        if info.get("valid"):
            discord = info.get("discord_name", "?")
            ip = info.get("current_ip", "?")
            days = info.get("session_ttl_days", 0)
            whitelisted = "Sim" if info.get("whitelisted") else "Nao"

            msg = f"{discord}\nIP: {ip}\nLiberado: {whitelisted}\nExpira em: {days} dias"
            update_icon_status("Conectado", f"{discord} | {days}d")
            show_notification("Status da Sessao", msg)
        else:
            update_icon_status("Desconectado", "Sem sessao ativa")
            show_notification("Status", "Nenhuma sessao ativa. Obtenha um codigo.")

    threading.Thread(target=do_check, daemon=True).start()


def on_open_portal(icon, item):
    """Abre o portal no navegador."""
    url = _config.get("portal_url", "https://shield.elysiusrp.com.br")
    webbrowser.open(url)


def on_open_config(icon, item):
    """Abre a pasta de configuração."""
    config_dir = CONFIG_FILE.parent
    config_dir.mkdir(parents=True, exist_ok=True)
    os.startfile(str(config_dir))


def on_open_log(icon, item):
    """Abre o arquivo de log."""
    if LOG_FILE.exists():
        os.startfile(str(LOG_FILE))


def on_clear_session(icon, item):
    """Limpa a sessão atual."""
    _config["session_token"] = ""
    _config["discord_name"] = ""
    save_config()
    update_icon_status("Desconectado", "Sessao limpa")
    show_notification("Sessao Limpa", "Sua sessao foi removida. Obtenha um novo codigo.")


def on_exit(icon, item):
    """Encerra o aplicativo."""
    global _running
    _running = False
    icon.stop()


def get_status_line():
    """Retorna a linha de status principal."""
    return f"Status: {_status}"


def get_detail_line():
    """Retorna detalhes do status."""
    return _status_detail if _status_detail else ""


def get_refresh_line():
    """Retorna a linha de ultima renovacao."""
    if _last_refresh:
        return f"Renovado: {_last_refresh.strftime('%H:%M:%S')}"
    return ""


def get_discord_line():
    """Retorna a linha do Discord."""
    if _config.get("discord_name"):
        return f"Discord: {_config['discord_name']}"
    return ""


def create_menu():
    """Cria o menu da system tray."""
    has_session = bool(_config.get("session_token"))

    return pystray.Menu(
        item(lambda text: get_status_line(), None, enabled=False),
        item(lambda text: get_detail_line(), None, enabled=False, visible=lambda i: bool(get_detail_line())),
        item(lambda text: get_discord_line(), None, enabled=False, visible=lambda i: bool(get_discord_line())),
        item(lambda text: get_refresh_line(), None, enabled=False, visible=lambda i: bool(get_refresh_line())),
        pystray.Menu.SEPARATOR,
        item("Obter Codigo", on_get_code, visible=lambda item: not _code_check_active),
        item("Forcar Novo Codigo", on_force_code, visible=lambda item: not _code_check_active),
        item("Renovar Agora", on_refresh_now, visible=lambda item: has_session),
        item("Verificar Status", on_check_status),
        item("Abrir Portal", on_open_portal),
        pystray.Menu.SEPARATOR,
        item("Abrir Configuracao", on_open_config),
        item("Ver Log", on_open_log),
        item("Limpar Sessao", on_clear_session, visible=lambda item: has_session),
        pystray.Menu.SEPARATOR,
        item("Sair", on_exit),
    )


def main():
    """Função principal."""
    global _icon, _running

    log.info("=" * 50)
    log.info("Iniciando %s", APP_NAME)
    log.info("=" * 50)

    # Carregar configuração
    load_config()

    log.info("Portal URL: %s", _config.get("portal_url"))
    log.info("Intervalo de renovacao: %ds", _config.get("refresh_interval", 60))
    log.info("Sessao existente: %s", "Sim" if _config.get("session_token") else "Nao")

    # Criar ícone
    initial_status = "Conectado" if _config.get("session_token") else "Desconectado"
    _icon = pystray.Icon(
        APP_NAME,
        create_icon_image("green" if _config.get("session_token") else "gray"),
        f"{APP_NAME} - {initial_status}",
        menu=create_menu(),
    )

    update_icon_status(initial_status, "Iniciando...")

    # Iniciar thread de renovação
    refresh_thread = threading.Thread(target=refresh_loop, daemon=True)
    refresh_thread.start()

    # Executar (bloqueia até icon.stop())
    log.info("Aplicativo iniciado - icone na system tray")
    _icon.run()

    log.info("Aplicativo encerrado")


if __name__ == "__main__":
    main()
