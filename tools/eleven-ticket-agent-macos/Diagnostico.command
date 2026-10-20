#!/bin/bash
set -euo pipefail
agent_root="$HOME/Library/Application Support/ElevenTickets"
echo "ELEVEN TICKETS — diagnóstico sem credenciais e sem impressão"
if /bin/launchctl print "gui/$(id -u)/com.eleven.tickets" >/dev/null 2>&1; then
  echo "Agente carregado no launchd."
else
  echo "Agente não está carregado. Abra Iniciar.command após configurar."
fi
if [ -f "$agent_root/agent.log" ]; then
  tail -30 "$agent_root/agent.log"
else
  echo "Ainda sem log. Execute Instalar.command."
fi
echo "Não envie config.json, journal.json, PDFs nem informações do Chaves."
read -r -p "Pressione Enter para fechar. "
