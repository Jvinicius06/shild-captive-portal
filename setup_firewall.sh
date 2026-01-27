#!/bin/bash
set -e

# --- CONFIGURAÇÕES DE PORTAS ---
IPSET_NAME="${IPSET_NAME:-jogadores_permitidos}"
GAME_PORT="${PROTECTED_PORTS:-30120}"

# Todas as suas portas de serviço (Web, API, Assets, Docker)
WEB_SERVICES="80,443,3000,3001,9090,4445"
SSH_PORT="22"

# --- LIMITES ---
GLOBAL_CONN_LIMIT=50         # Máximo de conexões TCP simultâneas por IP
WEB_PKT_LIMIT="2000/sec"     # Limite de pacotes para evitar flood nas APIs
WEB_BURST="200"

echo "[*] Iniciando blindagem das portas: $WEB_SERVICES e $GAME_PORT"

# 1. Garantir IPSET
ipset create "$IPSET_NAME" hash:ip -exist

# 2. Criar/Limpar nossa Chain customizada
if iptables -N FILTRO_CIDADE 2>/dev/null; then
    echo "[*] Chain FILTRO_CIDADE criada."
else
    iptables -F FILTRO_CIDADE
fi

# =========================================================
# REGRAS DE FILTRAGEM (Ordem de Execução)
# =========================================================

# A. Liberar o que já está conectado e tráfego interno
iptables -A FILTRO_CIDADE -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
iptables -A FILTRO_CIDADE -i lo -j ACCEPT

# B. PORTAS DO JOGO (Prioridade Total)
# Se o IP está no IPSet, ACEITA e ignora os limites abaixo.
IFS=',' read -ra GAME_PORTS <<< "$GAME_PORT"
for PORT in "${GAME_PORTS[@]}"; do
    PORT=$(echo "$PORT" | tr -d ' ')
    echo "[*] Protegendo porta do jogo: $PORT"
    iptables -A FILTRO_CIDADE -p tcp --dport "$PORT" -m set --match-set "$IPSET_NAME" src -j ACCEPT
    iptables -A FILTRO_CIDADE -p udp --dport "$PORT" -m set --match-set "$IPSET_NAME" src -j ACCEPT
    # Se NÃO está no IPSet e tentou a porta do jogo -> DROP
    iptables -A FILTRO_CIDADE -p tcp --dport "$PORT" -j DROP
    iptables -A FILTRO_CIDADE -p udp --dport "$PORT" -j DROP
done

# C. LIMITE GLOBAL DE 50 CONEXÕES (Para todo o resto)
# Protege 80, 443, 3000, 3001, 9090, 4445 e SSH contra excesso de sockets.
echo "[*] Aplicando trava de $GLOBAL_CONN_LIMIT conexões globais por IP..."
iptables -A FILTRO_CIDADE -p tcp --syn -m connlimit --connlimit-above $GLOBAL_CONN_LIMIT --connlimit-mask 32 -j DROP

# D. PROTEÇÃO ESPECÍFICA PARA WEB/APIs/DOCKER
# Aplica o limite de pacotes por segundo (PPS) individualmente por IP
iptables -A FILTRO_CIDADE -p tcp -m multiport --dports "$WEB_SERVICES" -m conntrack --ctstate NEW -m hashlimit --hashlimit-name limite_web --hashlimit-upto $WEB_PKT_LIMIT --hashlimit-burst $WEB_BURST --hashlimit-mode srcip -j ACCEPT

# E. PROTEÇÃO SSH
iptables -A FILTRO_CIDADE -p tcp --dport "$SSH_PORT" -m state --state NEW -m recent --set
iptables -A FILTRO_CIDADE -p tcp --dport "$SSH_PORT" -m state --state NEW -m recent --update --seconds 60 --hitcount 5 -j DROP
iptables -A FILTRO_CIDADE -p tcp --dport "$SSH_PORT" -j ACCEPT

# F. RETORNO
# Se o pacote não for de nenhuma dessas portas, ele volta para o fluxo padrão do sistema
iptables -A FILTRO_CIDADE -j RETURN

# =========================================================
# APLICAÇÃO NO HOST E NO DOCKER
# =========================================================

# Limpa hooks antigos para não duplicar
iptables -D INPUT -j FILTRO_CIDADE 2>/dev/null || true
iptables -D DOCKER-USER -j FILTRO_CIDADE 2>/dev/null || true

# Injeta no início do INPUT (Serviços rodando no Linux direto)
iptables -I INPUT 1 -j FILTRO_CIDADE

# Injeta no início do DOCKER-USER (Serviços rodando em Containers)
if iptables -L DOCKER-USER >/dev/null 2>&1; then
    iptables -I DOCKER-USER 1 -j FILTRO_CIDADE
    echo "[+] Regras integradas ao Docker com sucesso."
fi

# Salvar persistente
ipset save > /etc/ipset.conf 2>/dev/null || true
if command -v netfilter-persistent > /dev/null; then
    netfilter-persistent save
fi

echo "[!] Configuração finalizada. Portas protegidas: $WEB_SERVICES"
