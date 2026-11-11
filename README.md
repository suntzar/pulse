# pulse // cli & daemon

Rastreador de habitos e rotinas minimalista para terminal, com suporte a mapas de calor (heatmaps) estilo GitHub, adaptacao automatica a paleta de cores ANSI do terminal e API HTTP embutida para integracao com Agentes de IA, KWGT, WhatsApp e Discord.

Construido inteiramente com a biblioteca padrao do Python 3 (**zero dependencias externas**, sem necessidade de `venv` ou `pip`).

---

## Caracteristicas

- **Zero Dependencias:** Usa apenas modulos nativos (`sqlite3`, `http.server`, `shutil`, `datetime`, `json`).
- **Design Adaptativo:** Segue automaticamente as cores do tema do seu terminal (ZSH/Bash/Termux) e ajusta a largura da grade de semanas ao tamanho da janela.
- **Banco Local Unico:** Todos os dados ficam salvos em `~/.pulse.db` (SQLite3).
- **API HTTP Integrada:** Comando nativo para levantar um servidor REST leve para automacoes, widgets de celular e LLMs (Function Calling).

---

## Instalacao

Torne o script executavel e crie um link simbolico global:

~~bash
chmod +x ~/dev/python/habit-tracker/pulse.py
sudo ln -sf ~/dev/python/habit-tracker/pulse.py /usr/local/bin/pulse
~~

---

## Uso no Terminal (CLI)

Visualizar o painel principal com os mapas de calor:

~~bash
pulse
~~

Carregar dados de demonstracao (3 rotinas com historico de 1 ano):

~~bash
pulse demo
~~

### Gerenciar Rotinas

Criar uma nova rotina (`add <nome> [meta] [unidade] [cor]`):
- **Unidades especiais:** `min` (formata em horas/minutos), `check` (binario `[■]`), ou qualquer texto personalizado (`questoes`, `paginas`, `km`).
- **Cores disponiveis:** `verde`, `azul`, `amarelo`, `ciano`, `roxo`, `vermelho`.

~~bash
pulse add "DEEP WORK" 120 min verde
pulse add "ESTUDO DE EXATAS" 15 questoes azul
pulse add "TREINO DIARIO" 1 check amarelo
~~

Registrar progresso no dia de hoje (`do <id> [valor_adicional]`):

~~bash
# Conclui imediatamente uma tarefa binaria (ou preenche 100% da meta)
pulse do 3

# Soma 45 minutos na tarefa 01 e 5 questoes na tarefa 02
pulse do 1 45
pulse do 2 5
~~

Definir ou corrigir o valor exato de hoje (`set <id> <valor>`):

~~bash
# Zera o registro de hoje da tarefa 03
pulse set 3 0

# Define exatamente 120 minutos na tarefa 01
pulse set 1 120
~~

Remover uma rotina permanentemente:

~~bash
pulse rm 3
~~

---

## API HTTP & Integracao com IA / KWGT

O `pulse` possui um servidor HTTP embutido para permitir que IAs (Gemini, OpenAI, bots de WhatsApp/Discord) e widgets (KWGT no Android) leiam e alterem suas rotinas em tempo real.

### 1. Iniciar o Servidor API

~~bash
# Inicia na porta padrao 8000 (ou especifique outra porta, ex: pulse serve 9000)
pulse serve 8000
~~

### 2. Endpoints Disponiveis

#### Ler Estado Atual (`GET /api/status`)
Retorna um JSON pronto para consumo com os textos ja formatados para exibicao em widgets (KWGT) ou contexto de LLMs:

~~bash
curl http://localhost:8000/api/status
~~

Exemplo de resposta:

~~json
{
  "date": "2026-11-11",
  "completed_today": 2,
  "total_habits": 3,
  "summary": "2/3 concluidas",
  "habits": [
    {
      "id": 1,
      "name": "DEEP WORK",
      "goal": 120.0,
      "unit": "min",
      "color": "verde",
      "today_value": 135.0,
      "done_today": true,
      "streak": 18,
      "consistency_rate": 91,
      "total_value": 11040.0,
      "display_left": "2h15m / 2h00m hoje",
      "display_right": "91% · 184h total"
    }
  ]
}
~~

#### Registrar Progresso via URL (`GET /api/do`)
Ideal para botoes rapidos no KWGT ou automacoes simples:

~~bash
# Marca a tarefa 3 como concluida
curl "http://localhost:8000/api/do?id=3"

# Soma 30 minutos na tarefa 1
curl "http://localhost:8000/api/do?id=1&val=30"
~~

#### Webhooks JSON para Agentes de IA (`POST`)
Para conectar com Function Calling (Gemini API / bots), envie requisicoes `POST` com JSON:

~~bash
# Somar progresso
curl -X POST http://localhost:8000/api/do \
  -H "Content-Type: application/json" \
  -d '{"id": 1, "value": 45}'

# Definir valor exato
curl -X POST http://localhost:8000/api/set \
  -H "Content-Type: application/json" \
  -d '{"id": 2, "value": 15}'

# Criar nova rotina via IA
curl -X POST http://localhost:8000/api/add \
  -H "Content-Type: application/json" \
  -d '{"name": "LEITURA", "goal": 20, "unit": "paginas", "color": "roxo"}'
~~

### 3. Modo CLI JSON (Sem Servidor)
Caso o seu agente de IA ou script rode na mesma maquina que o `pulse`, ele pode ler o JSON diretamente via linha de comando sem precisar abrir portas de rede:

~~bash
pulse json
~~

---

## Estrutura do Banco de Dados

O arquivo `~/.pulse.db` contem duas tabelas SQLite:
- `habits`: `id`, `name`, `goal`, `unit`, `color`
- `logs`: `habit_id`, `date` (formato `YYYY-MM-DD`), `value`
