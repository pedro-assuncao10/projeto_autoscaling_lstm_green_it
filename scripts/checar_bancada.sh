#!/usr/bin/env bash
# Diagnóstico de viabilidade para medição energética com RAPL.
# Uso:  bash checar_bancada.sh
if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
elif sudo -v 2>/dev/null; then
  SUDO="sudo"
else
  SUDO=""
  SEM_ROOT=1
fi

echo "=========================================="
echo " DIAGNÓSTICO DE BANCADA — $(date '+%d/%m/%Y %H:%M')"
echo " host: $(hostname)"
echo "=========================================="

echo
echo "--- 1. SISTEMA ---"
. /etc/os-release 2>/dev/null && echo "distro : $PRETTY_NAME"
echo "kernel : $(uname -r)"
virt=$(systemd-detect-virt 2>/dev/null); [ -z "$virt" ] && virt="desconhecido"
echo "virtualização : $virt"
if [ "$virt" != "none" ] && [ "$virt" != "desconhecido" ]; then
  echo "  >> ATENÇÃO: é máquina virtual ($virt) — RAPL quase certamente indisponível"
fi

echo
echo "--- 2. PROCESSADOR ---"
grep -m1 "model name" /proc/cpuinfo | sed 's/model name\s*:/modelo :/'
echo "núcleos físicos : $(lscpu 2>/dev/null | awk -F: '/^Core\(s\) per socket|^Núcleo\(s\) por soquete/{gsub(/ /,"",$2);print $2}')"
echo "threads totais  : $(nproc)"
gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null || echo "n/d")
echo "governor        : $gov"
[ "$gov" != "performance" ] && [ "$gov" != "n/d" ] && echo "  >> para medir, fixe em 'performance' (evita variação de frequência)"

echo
echo "--- 3. MEMÓRIA E DISCO ---"
free -h | awk 'NR<=3'
echo "raiz: $(df -h / | tail -1 | awk '{print $4" livres de "$2}')"
sw=$(free -m | awk '/Swap|Troca/{print $3}')
[ "${sw:-0}" -gt 100 ] && echo "  >> swap em uso (${sw} MB): I/O de disco não aparece no RAPL e polui a medição"

echo
echo "--- 4. RAPL (o que decide tudo) ---"
if [ -d /sys/class/powercap/intel-rapl ]; then
  echo "powercap PRESENTE. Domínios:"
  for z in /sys/class/powercap/intel-rapl*/; do
    n=$(cat "$z/name" 2>/dev/null)
    [ -n "$n" ] && printf "   %-18s %-12s perm=%s\n" "$(basename $z)" "$n" "$(stat -c %a "$z/energy_uj" 2>/dev/null || echo '-')"
  done
  echo
  echo "leitura sem root:"; cat /sys/class/powercap/intel-rapl:0/energy_uj 2>&1 | head -1
  echo "leitura com sudo:"; ${SUDO:-sudo} cat /sys/class/powercap/intel-rapl:0/energy_uj 2>&1 | head -1
  echo
  echo "duas leituras com 3 s de intervalo (para estimar a potência ociosa):"
  a=$($SUDO cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null)
  sleep 3
  b=$($SUDO cat /sys/class/powercap/intel-rapl:0/energy_uj 2>/dev/null)
  if [ -n "$a" ] && [ -n "$b" ] && [ "$b" -gt "$a" ] 2>/dev/null; then
    awk -v d=$((b-a)) 'BEGIN{printf "   delta = %d uJ em 3 s  ->  %.2f W de potência média no pacote\n", d, d/3000000}'
    echo "   >> RAPL FUNCIONANDO — esta máquina serve"
  elif [ -n "$SEM_ROOT" ]; then
    echo "   >> sem sudo nesta execução. Rode:  sudo bash checar_bancada.sh"
  else
    echo "   >> contador não avançou — verificar driver"
  fi
else
  echo ">> powercap AUSENTE — esta máquina NÃO serve para medição RAPL"
fi

echo
echo "--- 5. FERRAMENTAS ---"
for c in docker kubectl kind k3s helm k6 python3 git curl ssh; do
  printf "   %-9s %s\n" "$c" "$(command -v $c 2>/dev/null || echo '(ausente)')"
done
groups | tr ' ' '\n' | grep -qx docker && echo "   usuário no grupo docker: sim" || echo "   usuário no grupo docker: NÃO"
if sudo -n true 2>/dev/null; then echo "   sudo: disponível"; elif [ -n "$SUDO" ]; then echo "   sudo: disponível (com senha)"; else echo "   sudo: INDISPONÍVEL — sem root não há medição"; fi

echo
echo "--- 6. REDE (para o k6 alcançar daqui) ---"
ip -4 addr show scope global 2>/dev/null | awk '/inet/{print "   "$NF": "$2}'
systemctl is-active ssh 2>/dev/null | grep -q active && echo "   ssh: ativo" || echo "   ssh: inativo/ausente (útil para acessar sem sentar na máquina)"

echo
echo "--- 7. AMBIENTE GRÁFICO ---"
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
  echo "   sessão gráfica ATIVA — durante as medições, prefira TTY/SSH com a GUI parada"
else
  echo "   sem sessão gráfica (ideal para medir)"
fi

echo
echo "=========================================="
echo " Traga esta saída inteira para a análise."
echo "=========================================="
