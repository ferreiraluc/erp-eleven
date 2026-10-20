#!/bin/bash
set -euo pipefail
agent_domain="gui/$(id -u)"
agent_plist="$HOME/Library/LaunchAgents/com.eleven.tickets.plist"
if /bin/launchctl print "$agent_domain/com.eleven.tickets" >/dev/null 2>&1; then
  echo "Eleven Tickets já está carregado. Nenhum trabalho foi reiniciado."
else
  /bin/launchctl bootstrap "$agent_domain" "$agent_plist"
  echo "Eleven Tickets iniciado em segundo plano."
fi
read -r -p "Pressione Enter para fechar. "
