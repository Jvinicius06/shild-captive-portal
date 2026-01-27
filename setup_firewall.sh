#!/bin/bash
set -e

IPSET_NAME="${IPSET_NAME:-jogadores_permitidos}"
PORT="${PROTECTED_PORTS:-30120}"

echo "[*] Creating ipset: $IPSET_NAME"
sudo ipset create "$IPSET_NAME" hash:ip -exist

echo "[*] Adding iptables ACCEPT rules for port $PORT"
sudo iptables -I INPUT -p tcp --dport "$PORT" -m set --match-set "$IPSET_NAME" src -j ACCEPT
sudo iptables -I INPUT -p udp --dport "$PORT" -m set --match-set "$IPSET_NAME" src -j ACCEPT

echo "[*] Adding iptables DROP rules for port $PORT"
sudo iptables -A INPUT -p tcp --dport "$PORT" -j DROP
sudo iptables -A INPUT -p udp --dport "$PORT" -j DROP

echo "[*] Saving rules"
sudo ipset save > /etc/ipset.conf 2>/dev/null || true
sudo iptables-save > /etc/iptables/rules.v4 2>/dev/null || sudo iptables-save > /etc/iptables.rules 2>/dev/null || true

echo "[+] Firewall setup complete. Port $PORT is now protected."
echo "[+] Only IPs in '$IPSET_NAME' can access port $PORT."
