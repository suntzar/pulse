# pulse // cli & daemon

Rastreador minimalista de rotinas diarias (heatmaps estilo GitHub) e tarefas unicas (lembretes/fila) para terminal, com adaptacao automatica a paleta de cores ANSI e API HTTP embutida para integracao com Agentes de IA, KWGT, WhatsApp e Discord.

Construido inteiramente com a biblioteca padrao do Python 3 (**zero dependencias externas**, sem necessidade de `venv` ou `pip`).

---

## Caracteristicas

- **Zero Dependencias:** Usa apenas modulos nativos (`sqlite3`, `http.server`, `shutil`, `datetime`, `json`).
- **Design Adaptativo:** Segue automaticamente as cores do tema do seu terminal (ZSH/Bash/Termux) e ajusta a largura da grade de semanas ao tamanho da janela.
- **Rotinas + Tarefas Unicas:** Combina habitos recorrentes (com mapa de calor e ofensiva) e lembretes pontuais (ex: pagar fatura, comprar sapatos, inscricao de prova) na mesma tela.
- **Banco Local Unico:** Todos os dados ficam salvos em `~/.pulse.db` (SQLite3).
- **API HTTP Integrada:** Servidor REST nativo para automacoes, widgets de celular e LLMs (Function Calling).

---

## Instalacao

Torne o script executavel e crie um link simbolico global:

```bash
chmod +x ~/dev/python/habit-tracker/pulse.py
sudo ln -sf ~/dev/python/habit-tracker/pulse.py /usr/local/bin/pulse
```

---

## Uso no Terminal (CLI)

Visualizar o painel completo (rotinas + tarefas unicas):

```bash
pulse
```

Carregar dados de demonstracao (3 rotinas com historico + 3 tarefas unicas):

```bash
pulse demo
```

### 1. Gerenciar Rotinas Diarias (Heatmaps)

Criar uma nova rotina (`add <nome> [meta] [unidade] [cor]`):
- **Unidades especiais:** `min` (formata em horas/minutos), `check` (binario `[■]`), ou qualquer texto personalizado (`questoes`, `paginas`, `km`).
- **Cores disponiveis:** `verde`, `azul`, `amarelo`, `ciano`, `roxo`, `vermelho`.

```bash
pulse add "DEEP WORK" 120 min verde
pulse add "ESTUDO DE EXATAS" 15 questoes azul
pulse add "TREINO DIARIO" 1 check amarelo
```

Registrar progresso no dia de hoje (`do <id> [valor_adicional]`):

```bash
pulse do 3
pulse do 1 45
pulse do 2 5
```

Definir ou corrigir o valor exato de hoje (`set <id> <valor>`):

```bash
pulse set 3 0
pulse set 1 120
```

Remover uma rotina permanentemente:

```bash
pulse rm 3
```

### 2. Gerenciar Tarefas Unicas (Lembretes / Fila)

Adicionar uma tarefa unica (`t <titulo> [prazo_ou_nota] [cor]`):
- Notas como `hoje`, `urgente` ou `agora` recebem destaque automatico na cor da tarefa.

```bash
pulse t "Pagar fatura do cartao" hoje vermelho
pulse t "Fazer inscricao na prova" "15 nov" amarelo
pulse t "Comprar sapatos"
```

Marcar como concluida ou reabrir (`td <id>`):

```bash
pulse td 1
```

Limpar da tela todas as tarefas ja concluidas ou remover uma especifica:

```bash
# Remove todas as tarefas marcadas como [■] concluido
pulse tclear

# Remove uma tarefa especifica pelo ID
pulse trm 2
```

---

## API HTTP & Integracao com IA / KWGT

### 1. Iniciar o Servidor API

```bash
pulse serve 8000
```

### 2. Endpoints Disponiveis

#### Ler Estado Atual (`GET /api/status`)
Retorna tanto as rotinas quanto a fila de tarefas unicas:

```bash
curl http://localhost:8000/api/status
```

#### Acoes Rapidas via URL (`GET`)

```bash
# Rotina: Marca a rotina 3 como concluida ou soma valor na rotina 1
curl "http://localhost:8000/api/do?id=3"
curl "http://localhost:8000/api/do?id=1&val=30"

# Tarefa Unica: Alterna concluido/pendente na tarefa 1
curl "http://localhost:8000/api/tdo?id=1"
```

#### Webhooks JSON para Agentes de IA (`POST`)

```bash
# Adicionar tarefa unica via IA (WhatsApp/Discord)
curl -X POST http://localhost:8000/api/tadd \
  -H "Content-Type: application/json" \
  -d '{"title": "PAGAR CARTAO", "note": "hoje", "color": "vermelho"}'

# Concluir tarefa unica
curl -X POST http://localhost:8000/api/tdo \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'

# Limpar tarefas concluidas
curl -X POST http://localhost:8000/api/tclear
```

---

## Estrutura do Banco de Dados (`~/.pulse.db`)

- `habits`: `id`, `name`, `goal`, `unit`, `color`
- `logs`: `habit_id`, `date` (`YYYY-MM-DD`), `value`
- `tasks`: `id`, `title`, `note`, `color`, `done` (`0` ou `1`), `created_at`
