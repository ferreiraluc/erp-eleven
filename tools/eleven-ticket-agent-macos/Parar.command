#!/bin/bash
set -euo pipefail
echo "Aguarde o ticket atual terminar. Parar no meio de um envio deixa o resultado incerto."
read -r -p "Pressione Enter para parar, ou Ctrl+C para cancelar. "
/bin/launchctl bootout "gui/$(id -u)/com.eleven.tickets" 2>/dev/null || true
echo "Parado. O diário e a fila foram preservados. Para retomar, abra Iniciar.command."
read -r -p "Pressione Enter para fechar. "
