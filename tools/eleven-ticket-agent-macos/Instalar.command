#!/bin/bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
if [ "$(uname -s)" != Darwin ]; then
  echo "Este instalador é exclusivo do macOS."; exit 1
fi
if [ "$(id -u)" = 0 ]; then
  echo "Abra como o usuário do caixa, sem sudo."; exit 1
fi
agent_root="$HOME/Library/Application Support/ElevenTickets"
agent_plist="$HOME/Library/LaunchAgents/com.eleven.tickets.plist"
agent_service="gui/$(id -u)/com.eleven.tickets"
trap 'echo "Se houve erro, anote a mensagem. Não apague config.json nem journal.json."; read -r -p "Pressione Enter para fechar. " || true' EXIT
test -f ./eleven-tickets || { echo "Pacote incompleto. Extraia todo o ZIP."; exit 1; }
/usr/bin/shasum -a 256 -c SHA256SUMS
/usr/bin/codesign --verify --deep --strict ./eleven-tickets
echo "Instalação para 3nStar RPT006W, Ethernet 192.168.123.100:9100."
echo "Ethernet do iMac: 192.168.123.10. Internet do ERP pode permanecer no Wi-Fi."
echo "A instalação preserva os outros agentes e não imprime."
echo "Em atualizações, aguarde terminar o ticket em andamento antes de continuar."
read -r -p "Pressione Enter para instalar, ou Ctrl+C para cancelar. "
# Stop only this launch agent. No spooler, Windows service, queue or network setting is changed.
/bin/launchctl bootout "$agent_service" 2>/dev/null || true
mkdir -p "$agent_root" "$HOME/Library/LaunchAgents"
chmod 700 "$agent_root"
# The binary itself takes an exclusive lock before configuring. A hung old
# process therefore fails closed instead of running two instances.
cp ./eleven-tickets "$agent_root/eleven-tickets.new"
chmod 700 "$agent_root/eleven-tickets.new"
mv -f "$agent_root/eleven-tickets.new" "$agent_root/eleven-tickets"
cp ./Iniciar.command ./Parar.command ./Diagnostico.command "$agent_root/"
chmod 700 "$agent_root/"*.command
"$agent_root/eleven-tickets" --configure
# PlistBuddy writes paths as data; user-directory characters never become XML or shell code.
rm -f "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Clear dict' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :Label string com.eleven.tickets' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :ProgramArguments array' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c "Add :ProgramArguments:0 string $agent_root/eleven-tickets" "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :ProgramArguments:1 string --run' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :RunAtLoad bool true' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :KeepAlive bool true' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :ThrottleInterval integer 30' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :ExitTimeOut integer 40' "$agent_plist.tmp"
/usr/libexec/PlistBuddy -c 'Add :ProcessType string Background' "$agent_plist.tmp"
/usr/bin/plutil -lint "$agent_plist.tmp"
chmod 600 "$agent_plist.tmp"
mv -f "$agent_plist.tmp" "$agent_plist"
/bin/launchctl bootstrap "gui/$(id -u)" "$agent_plist"
echo "Instalado e iniciado em segundo plano. Iniciará automaticamente ao entrar nesta conta do Mac."
echo "Agora peça o teste no ERP. Ative a 3nStar somente depois de conferir o papel."
echo "Pode fechar esta janela. O iMac precisa permanecer ligado, acordado e com esta sessão iniciada."
