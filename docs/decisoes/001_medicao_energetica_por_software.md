# Decisão 001 — Medição energética somente por software

**Data:** 14/09/2026
**Status:** aceita

---

## Contexto

O projeto precisa medir o consumo de energia da aplicação para comparar o
autoscaler preditivo com o HPA reativo.

Existem duas famílias de medição:

| Família | Exemplos | Exige |
|---|---|---|
| **Hardware** | medidor de tomada, iDRAC/Redfish, PDU instrumentada | acesso físico ou controlador de gerenciamento do servidor |
| **Software** | RAPL (via Scaphandre, Kepler, KubeWatt) | acesso aos contadores do processador no sistema operacional |

O KubeWatt (Pijnacker et al., 2025) usou o iDRAC como referência e o validou com um
medidor de tomada. Esse caminho exige hardware específico e acesso físico.

## Decisão

1. **A medição será feita somente por software, via RAPL.** Nenhum medidor de tomada
   ou instrumentação física será usado.
2. **O servidor sob teste será o PC do laboratório** (máquina física, acessada
   remotamente). Servidor dedicado alugado fica como alternativa, fora do orçamento atual.
3. **A atribuição de energia por container seguirá o modelo estático/dinâmico do
   KubeWatt**, aplicado sobre os dados do RAPL. Reaproveita-se o **modelo**, não o código.

## Justificativa

- O foco da dissertação é **software**: a decisão de escala, não a infraestrutura física.
- A comparação é **relativa** — dois algoritmos, mesmo hardware, mesmo instrumento.
  O RAPL é adequado para comparação relativa (Khan et al., 2018).
- A metodologia deve ser reproduzível por qualquer pessoa, sem hardware especial.
- Ler o RAPL **é software**: é ler um arquivo em `/sys`. Não exige nenhuma peça.

## Requisito obrigatório do servidor

> ⚠️ **Máquina virtual de nuvem comum NÃO serve.** AWS EC2, GCP, Azure, Hetzner Cloud,
> DigitalOcean etc. não expõem RAPL dentro da VM (o hipervisor não repassa os
> contadores, por segurança — ataque PLATYPUS, CVE-2020-8694). Mesmo que expusessem,
> o consumo do socket incluiria outros clientes.

O servidor precisa ser **dedicado / bare metal**, por exemplo:

- Servidores dedicados: Hetzner (Robot), OVH, Scaleway Dedibox, Equinix Metal
- Instâncias `*.metal` da AWS (caras)
- **Máquina física do laboratório acessada remotamente ← escolhida**

**Antes de contratar**, verificar com cobrança por hora:

```bash
ls /sys/class/powercap/                               # deve listar intel-rapl
sudo cat /sys/class/powercap/intel-rapl:0/energy_uj   # deve devolver um número
sudo bash scripts/checar_bancada.sh                   # diagnóstico completo
```

Preferência: **processador Intel** (expõe o domínio `dram`; AMD expõe só `package` e `core`).

## Consequências

### O que ganhamos
- Montagem reproduzível por qualquer pessoa, sem hardware especial
- Foco no que a dissertação realmente estuda
- Instrumento que qualquer pessoa consegue replicar

### O que perdemos (declarar como limitação no Capítulo IV)
- **Sem referência física (ground truth).** Não será possível afirmar o erro absoluto da medição.
- **RAPL mede só o processador** (e memória, em Intel). Ficam fora: disco, rede,
  ventoinhas, placa-mãe, fonte. Um servidor que reporta 40 W de pacote pode puxar 120 W da tomada.
- **RAPL é um modelo interno do processador**, não um wattímetro.

### Como reportar corretamente
- Nunca escrever "consumo do servidor". Escrever **"energia do pacote do processador"**.
- Métrica principal: **joules por requisição** e **gCO₂e por requisição** (SCI).
- Separar sempre **potência estática** (paga de qualquer jeito) de **dinâmica**
  (a única que o autoscaler influencia).

## Mitigações sem hardware

1. **Validação cruzada entre ferramentas:** comparar RAPL bruto, Scaphandre e
   KubeWatt-RAPL no mesmo teste. Divergência grande indica problema de atribuição.
2. **Conferência de soma:** a soma da energia atribuída aos containers + a parte
   estática deve bater com o total do RAPL.
3. **Teste de containers ociosos** (replicar o do KubeWatt): containers parados devem
   receber zero de potência dinâmica.
4. **Medição da linha de base ociosa** antes de cada sessão.
5. **Repetições com intervalo de confiança** (≥ 15 execuções, IC 95%, como o CarbonScaler).
6. **Governor fixo em `performance`** e ambiente sem tarefas concorrentes
   (ver `scripts/preparar_server.sh`).

## Implementação da medição

**Não** será escrito um coletor para a ferramenta KubeWatt (ela é em Java e exige
iDRAC/Redfish). Em vez disso, reaproveitando o que já existe:

| Peça | Ferramenta |
|---|---|
| Total do nó (referência) | leitor RAPL próprio, ~50 linhas de Python |
| Atribuição por processo | Scaphandre |
| Atribuição por pod | fórmula estático/dinâmico do KubeWatt, na consolidação dos dados |

Cuidados do leitor RAPL:

- `energy_uj` é um **contador acumulado** em microjoules: potência = Δenergia / Δtempo
- O contador **dá a volta** (*wraparound*) ao atingir `max_energy_range_uj`
- Leitura exige root
- Agregar múltiplos sockets (`intel-rapl:0`, `intel-rapl:1`, …)

Detalhes em `docs/pipeline.md`, Fases 2 e 3.

## Referências

- PIJNACKER, B.; SETZ, B.; ANDRIKOPOULOS, V. *Container-level Energy Observability in
  Kubernetes Clusters.* arXiv:2504.10702, 2025. Código: github.com/bjornpijnacker/kubewatt
- KHAN, K. N. et al. *RAPL in Action: Experiences in Using RAPL for Power Measurements.*
  ACM ToMPECS, v. 3, n. 2, 2018.
- CENTOFANTI, C. et al. *Impact of power consumption in containerized clouds: A
  comprehensive analysis of open-source power measurement tools.* Computer Networks,
  v. 245, 2024.
- Resumo: `revisao_bibliografica/resumos/03_kubewatt.md`
