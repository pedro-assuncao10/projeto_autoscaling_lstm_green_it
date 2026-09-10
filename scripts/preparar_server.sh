#!/usr/bin/env bash
# Prepara uma máquina de laboratório para servir de sistema sob teste (SUT).
# Por padrão apenas MOSTRA o que faria. Para aplicar de fato:  sudo bash preparar_server.sh --aplicar
set -u
APLICAR=0
[ "${1:-}" = "--aplicar" ] && APLICAR=1

exec_ou_mostra() {
  local desc="$1"; shift
  if [ $APLICAR -eq 1 ]; then
    printf "  [aplicando] %s\n" "$desc"
    "$@" >/dev/null 2>&1 && echo "              ok" || echo "              FALHOU"
  else
    printf "  [simulação] %s\n              -> %s\n" "$desc" "$*"
  fi
}

echo "=================================================="
[ $APLICAR -eq 1 ] && echo " MODO: APLICANDO ALTERAÇÕES" || echo " MODO: SIMULAÇÃO (nada será alterado)"
echo "=================================================="

if [ $APLICAR -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "Erro: para aplicar, rode com sudo."; exit 1
fi

echo
echo "--- 1. Impedir que a máquina durma no meio do experimento ---"
echo "  estado atual: $(systemctl is-enabled sleep.target 2>/dev/null || echo n/d)"
exec_ou_mostra "mascarar suspensão e hibernação" \
  systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
echo "  reverter com: sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target"

echo
echo "--- 2. Fixar a frequência do processador ---"
echo "  governor atual: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo n/d)"
echo "  disponíveis   : $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors 2>/dev/null || echo n/d)"
if [ $APLICAR -eq 1 ]; then
  for c in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$c" 2>/dev/null; done
  echo "  [aplicando] governor -> performance (ok em $(nproc) CPUs)"
  echo "              ATENÇÃO: não persiste no reboot; refaça antes de cada sessão de medição"
else
  echo "  [simulação] escreveria 'performance' em todos os cpu*/cpufreq/scaling_governor"
fi

echo
echo "--- 3. Silenciar tarefas automáticas durante as medições ---"
for t in apt-daily.timer apt-daily-upgrade.timer unattended-upgrades.service man-db.timer; do
  st=$(systemctl is-active "$t" 2>/dev/null); [ -z "$st" ] && st="não encontrado"
  printf "  %-32s %s\n" "$t:" "$st"
done
exec_ou_mostra "parar timers do apt" systemctl stop apt-daily.timer apt-daily-upgrade.timer
echo "  reverter com: sudo systemctl start apt-daily.timer apt-daily-upgrade.timer"

echo
echo "--- 4. Acesso remoto (para você rodar do notebook) ---"
if systemctl is-active ssh >/dev/null 2>&1 || systemctl is-active sshd >/dev/null 2>&1; then
  echo "  ssh: já ativo"
else
  echo "  ssh: inativo"
  exec_ou_mostra "instalar e habilitar o servidor ssh" \
    bash -c "apt-get install -y openssh-server && systemctl enable --now ssh"
fi
ip -4 addr show scope global 2>/dev/null | awk '/inet/{print "  endereço: "$2" ("$NF")"}'
echo "  >> peça um IP fixo (ou reserva de DHCP) ao responsável pela rede:"
echo "     se o IP mudar no meio da pesquisa, seus scripts de carga perdem o alvo"

echo
echo "--- 5. Interface gráfica ---"
alvo=$(systemctl get-default 2>/dev/null)
echo "  alvo de boot atual: $alvo"
if [ "$alvo" = "graphical.target" ]; then
  echo "  >> a GUI consome CPU e entra na sua medição."
  echo "     Para desligar só durante o experimento (reversível, sem reboot):"
  echo "       sudo systemctl isolate multi-user.target     # desliga a GUI agora"
  echo "       sudo systemctl isolate graphical.target      # devolve a GUI"
  echo "     NÃO vou alterar o alvo padrão: é máquina compartilhada, outra pessoa pode precisar da GUI."
fi

echo
echo "--- 6. Swap ---"
free -m | awk '/Swap|Troca/{printf "  swap: %s MB em uso de %s MB\n", $3, $2}'
echo "  >> se houver swap ativo durante a medição, o I/O de disco não aparece no RAPL"
echo "     e a sua conta de energia por requisição fica subestimada."
echo "     Se a máquina tiver RAM sobrando, considere:  sudo swapoff -a  (reverter: sudo swapon -a)"

echo
echo "=================================================="
[ $APLICAR -eq 0 ] && echo " Nada foi alterado. Para aplicar: sudo bash $0 --aplicar"
echo "=================================================="
