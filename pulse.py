#!/usr/bin/env python3
import sys
import json
import sqlite3
import shutil
import datetime
import random
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = Path.home() / ".pulse.db"

CORES = {
    "verde": "32",
    "azul": "34",
    "amarelo": "33",
    "ciano": "36",
    "roxo": "35",
    "vermelho": "31",
}

def c(txt: str, codigos: str = "") -> str:
    return f"\033[{codigos}m{txt}\033[0m" if codigos else txt

# --- BANCO DE DADOS ---
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            goal REAL NOT NULL DEFAULT 1,
            unit TEXT NOT NULL DEFAULT 'check',
            color TEXT NOT NULL DEFAULT 'verde'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            habit_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            value REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (habit_id, date),
            FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE
        )
    """)
    return conn

# --- REGRAS DE NEGÓCIO ---
def formatar_tempo(minutos: float) -> str:
    m = int(round(minutos))
    return f"{m // 60}h{m % 60:02d}m"

def calcular_nivel(val: float, goal: float, unit: str) -> int:
    if val <= 0:
        return 0
    if unit == "check" or goal <= 1:
        return 3
    ratio = val / goal
    if ratio < 0.5:
        return 1
    elif ratio < 1.0:
        return 2
    return 3

def calcular_streak(logs_map: dict, hoje: datetime.date) -> int:
    streak = 0
    cursor = hoje if logs_map.get(hoje.isoformat(), 0) > 0 else hoje - datetime.timedelta(days=1)
    while logs_map.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return streak

def formatar_status(val_hoje: float, goal: float, unit: str, rate: int, total_val: float) -> tuple[str, str]:
    if unit == "min":
        esq = f"{formatar_tempo(val_hoje)} / {formatar_tempo(goal)} hoje"
        dir_s = f"{rate}% · {int(total_val // 60)}h total"
    elif unit == "check":
        esq = "concluido hoje" if val_hoje >= goal else "pendente hoje"
        marca = "[■]" if val_hoje >= goal else "[ ]"
        dir_s = f"{marca} hoje · {rate}%"
    else:
        v_int = int(val_hoje) if val_hoje.is_integer() else val_hoje
        g_int = int(goal) if goal.is_integer() else goal
        esq = f"{v_int}/{g_int} {unit}"
        blocos_p = min(5, int(round((val_hoje / goal) * 5))) if goal > 0 else 0
        barra = ("■" * blocos_p) + ("·" * (5 - blocos_p))
        pct_hoje = int(round((val_hoje / goal) * 100)) if goal > 0 else 0
        dir_s = f"[{barra}] {pct_hoje}%"
    return esq, dir_s

# --- SERIALIZAÇÃO PARA API / IA / KWGT ---
def obter_estado_completo(conn: sqlite3.Connection, semanas_calculo: int = 16) -> dict:
    hoje = datetime.date.today()
    hoje_iso = hoje.isoformat()
    hoje_idx = hoje.weekday()
    total_dias = ((semanas_calculo - 1) * 7) + (hoje_idx + 1)

    habits = conn.execute("SELECT * FROM habits ORDER BY id ASC").fetchall()
    lista_habitos = []
    concluidas_hoje = 0

    for h in habits:
        rows = conn.execute("SELECT date, value FROM logs WHERE habit_id = ?", (h["id"],)).fetchall()
        mapa = {r["date"]: r["value"] for r in rows}

        val_hoje = mapa.get(hoje_iso, 0.0)
        meta_batida = val_hoje >= h["goal"]
        if meta_batida:
            concluidas_hoje += 1

        streak = calcular_streak(mapa, hoje)
        dias_ativos = sum(
            1 for d in range(total_dias)
            if mapa.get((hoje - datetime.timedelta(days=d)).isoformat(), 0) > 0
        )
        rate = int(round((dias_ativos / max(1, total_dias)) * 100))
        total_val = sum(mapa.values())
        status_esq, status_dir = formatar_status(val_hoje, h["goal"], h["unit"], rate, total_val)

        lista_habitos.append({
            "id": h["id"],
            "name": h["name"],
            "goal": h["goal"],
            "unit": h["unit"],
            "color": h["color"],
            "today_value": val_hoje,
            "done_today": meta_batida,
            "streak": streak,
            "consistency_rate": rate,
            "total_value": total_val,
            "display_left": status_esq,
            "display_right": status_dir,
            "logs": mapa,
        })

    return {
        "date": hoje_iso,
        "completed_today": concluidas_hoje,
        "total_habits": len(habits),
        "summary": f"{concluidas_hoje}/{len(habits)} concluidas",
        "habits": lista_habitos,
    }

# --- OPERAÇÕES DE BANCO ---
def acao_do(conn: sqlite3.Connection, h_id: int, val_extra: float | None = None) -> bool:
    hoje_iso = datetime.date.today().isoformat()
    habit = conn.execute("SELECT * FROM habits WHERE id = ?", (h_id,)).fetchone()
    if not habit:
        return False
    atual = conn.execute("SELECT value FROM logs WHERE habit_id = ? AND date = ?", (h_id, hoje_iso)).fetchone()
    val_atual = atual["value"] if atual else 0.0
    novo_val = (val_atual + val_extra) if val_extra is not None else habit["goal"]
    conn.execute("INSERT OR REPLACE INTO logs (habit_id, date, value) VALUES (?, ?, ?)", (h_id, hoje_iso, novo_val))
    conn.commit()
    return True

def acao_set(conn: sqlite3.Connection, h_id: int, val: float) -> bool:
    hoje_iso = datetime.date.today().isoformat()
    if val <= 0:
        conn.execute("DELETE FROM logs WHERE habit_id = ? AND date = ?", (h_id, hoje_iso))
    else:
        conn.execute("INSERT OR REPLACE INTO logs (habit_id, date, value) VALUES (?, ?, ?)", (h_id, hoje_iso, val))
    conn.commit()
    return True

def acao_add(conn: sqlite3.Connection, nome: str, meta: float = 1.0, unid: str = "check", cor: str = "verde") -> int:
    cur = conn.execute(
        "INSERT INTO habits (name, goal, unit, color) VALUES (?, ?, ?, ?)",
        (nome.upper(), meta, unid.lower(), cor.lower()),
    )
    conn.commit()
    return cur.lastrowid

def acao_rm(conn: sqlite3.Connection, h_id: int):
    conn.execute("DELETE FROM logs WHERE habit_id = ?", (h_id,))
    conn.execute("DELETE FROM habits WHERE id = ?", (h_id,))
    conn.commit()

# --- RENDERIZAÇÃO DO TERMINAL (CLI) ---
def render_dashboard(conn: sqlite3.Connection):
    PADDING = 4
    MARGEM = " " * PADDING
    largura_terminal = shutil.get_terminal_size((42, 20)).columns
    espaco_util = largura_terminal - (PADDING * 2) - 4
    SEMANAS = max(4, min(52, espaco_util // 2))
    LARGURA_APP = 4 + (SEMANAS * 2)

    estado = obter_estado_completo(conn, SEMANAS)
    habits = estado["habits"]

    if not habits:
        print(f"\n    {c('Nenhuma rotina cadastrada.', '2')}")
        print(f"    Crie uma com: {c('pulse add \"DEEP WORK\" 120 min verde', '1')}")
        print(f"    Ou carregue exemplos com: {c('pulse demo', '1')}\n")
        return

    hoje = datetime.date.today()
    dias_semana = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
    meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    data_atual = f"{dias_semana[hoje.weekday()]} {hoje.day} {meses[hoje.month - 1]}"
    hoje_idx = hoje.weekday()

    def alinhar(esq_raw: str, esq_fmt: str, dir_raw: str, dir_fmt: str) -> str:
        espacos = max(1, LARGURA_APP - len(esq_raw) - len(dir_raw))
        return f"{MARGEM}{esq_fmt}{' ' * espacos}{dir_fmt}"

    print()
    txt_esq_1 = "pulse"
    txt_esq_2 = f" // {data_atual}"
    txt_dir = estado["summary"]

    esq_raw = txt_esq_1 + txt_esq_2
    esq_fmt = f"{c(txt_esq_1, '1')}{c(txt_esq_2, '2')}"
    print(alinhar(esq_raw, esq_fmt, txt_dir, c(txt_dir, "2")))

    espacos_meio = max(1, LARGURA_APP - len(esq_raw) - len(txt_dir))
    linha = (
        c("━" * len(txt_esq_1), "1")
        + c("━" * len(txt_esq_2), "2")
        + c("━" * espacos_meio, "2")
        + c("━" * len(txt_dir), "2")
    )
    print(f"{MARGEM}{linha}\n")

    dias_letras = ["s", "t", "q", "q", "s", "s", "d"]

    for h in habits:
        cb = CORES.get(h["color"], "32")
        tons = ["2", f"2;{cb}", cb, f"1;{cb}"]
        mapa = h["logs"]
        id_str = f"{h['id']:02d}"
        nome_upper = h["name"].upper()

        esq_1_raw = f"█ {id_str}  {nome_upper}"
        esq_1_fmt = f"{c('█', cb)} {c(id_str, f'1;{cb}')}  {c(nome_upper, '1')}"
        dir_1_raw = f"{h['streak']}d seq"
        dir_1_fmt = f"{c(f\"{h['streak']}d\", f'1;{cb}')} {c('seq', '2')}"
        print(alinhar(esq_1_raw, esq_1_fmt, dir_1_raw, dir_1_fmt))

        status_esq, status_dir = h["display_left"], h["display_right"]
        cor_status = f"1;{cb}" if h["today_value"] > 0 else "2"
        print(alinhar(f"    {status_esq}", f"    {c(status_esq, cor_status)}", status_dir, c(status_dir, "2")))

        for dia_idx, letra in enumerate(dias_letras):
            rotulo = c(letra, "2") if dia_idx in (0, 2, 4, 6) else " "
            blocos = []

            for sem in range(SEMANAS):
                dias_atras = (SEMANAS - 1 - sem) * 7 + (hoje_idx - dia_idx)
                if dias_atras < 0:
                    blocos.append(c("·", "2"))
                else:
                    dt_iso = (hoje - datetime.timedelta(days=dias_atras)).isoformat()
                    val = mapa.get(dt_iso, 0.0)
                    nivel = calcular_nivel(val, h["goal"], h["unit"])
                    blocos.append(c("■", tons[nivel]))

            print(f"{MARGEM}{rotulo}  {' '.join(blocos)}")

        print()

# --- SERVIDOR HTTP REST API (ZERO DEPENDÊNCIAS) ---
class PulseAPIHandler(BaseHTTPRequestHandler):
    def _responder_json(self, dados: dict, status: int = 200):
        corpo = json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, format, *args):
        # Log limpo no terminal quando o servidor recebe requisições
        print(f"  {c('api', '1;32')} // {self.address_string()} -> {format % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        conn = get_db()

        if parsed.path in ("/", "/api/status"):
            estado = obter_estado_completo(conn)
            for h in estado["habits"]:
                del h["logs"]  # Mantém o JSON leve para KWGT e IA
            self._responder_json(estado)

        elif parsed.path == "/api/do" and "id" in params:
            h_id = int(params["id"][0])
            val = float(params["val"][0]) if "val" in params else None
            ok = acao_do(conn, h_id, val)
            self._responder_json({"ok": ok, "state": obter_estado_completo(conn)}, 200 if ok else 404)

        elif parsed.path == "/api/set" and "id" in params and "val" in params:
            ok = acao_set(conn, int(params["id"][0]), float(params["val"][0]))
            self._responder_json({"ok": ok, "state": obter_estado_completo(conn)})

        else:
            self._responder_json({"error": "Rota nao encontrada"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        tamanho = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(tamanho).decode("utf-8")) if tamanho > 0 else {}
        conn = get_db()

        if parsed.path == "/api/do" and "id" in body:
            val = float(body["value"]) if "value" in body else None
            ok = acao_do(conn, int(body["id"]), val)
            self._responder_json({"ok": ok}, 200 if ok else 404)

        elif parsed.path == "/api/set" and "id" in body and "value" in body:
            acao_set(conn, int(body["id"]), float(body["value"]))
            self._responder_json({"ok": True})

        elif parsed.path == "/api/add" and "name" in body:
            novo_id = acao_add(
                conn,
                body["name"],
                float(body.get("goal", 1.0)),
                body.get("unit", "check"),
                body.get("color", "verde"),
            )
            self._responder_json({"ok": True, "id": novo_id}, 201)

        elif parsed.path == "/api/rm" and "id" in body:
            acao_rm(conn, int(body["id"]))
            self._responder_json({"ok": True})

        else:
            self._responder_json({"error": "Payload invalido ou rota inexistente"}, 400)

def popular_demo(conn: sqlite3.Connection):
    conn.execute("DELETE FROM logs")
    conn.execute("DELETE FROM habits")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='habits'")

    demos = [
        ("DEEP WORK", 120, "min", "verde", [0.08, 0.15, 0.42, 0.35], 18, 135),
        ("ESTUDO DE EXATAS", 15, "questoes", "azul", [0.22, 0.25, 0.33, 0.20], 6, 12),
        ("TREINO DIARIO", 1, "check", "amarelo", [0.36, 0.0, 0.0, 0.64], 4, 0),
    ]
    hoje = datetime.date.today()

    for nome, meta, unid, cor, pesos, streak, val_hoje in demos:
        h_id = acao_add(conn, nome, meta, unid, cor)
        random.seed(h_id)

        for d in range(1, 365):
            dt = (hoje - datetime.timedelta(days=d)).isoformat()
            lvl = (random.choice([2, 3]) if unid != "check" else 3) if d <= streak else random.choices([0, 1, 2, 3], weights=pesos)[0]
            if lvl > 0:
                val = meta * (0.4 if lvl == 1 else (0.8 if lvl == 2 else 1.1)) if unid != "check" else 1
                conn.execute("INSERT INTO logs (habit_id, date, value) VALUES (?, ?, ?)", (h_id, dt, round(val)))

        if val_hoje > 0:
            conn.execute("INSERT INTO logs (habit_id, date, value) VALUES (?, ?, ?)", (h_id, hoje.isoformat(), val_hoje))

    conn.commit()

def main():
    conn = get_db()
    args = sys.argv[1:]

    if not args:
        render_dashboard(conn)
        return

    cmd = args[0].lower()

    if cmd in ("do", "check", "c") and len(args) >= 2:
        val = float(args[2]) if len(args) >= 3 else None
        if not acao_do(conn, int(args[1]), val):
            print(c(f"  Erro: Tarefa {int(args[1]):02d} nao encontrada.", "31"))
            return
        render_dashboard(conn)

    elif cmd == "set" and len(args) >= 3:
        acao_set(conn, int(args[1]), float(args[2]))
        render_dashboard(conn)

    elif cmd == "add" and len(args) >= 2:
        nome = args[1]
        meta = float(args[2]) if len(args) >= 3 else 1.0
        unid = args[3] if len(args) >= 4 else "check"
        cor = args[4] if len(args) >= 5 else "verde"
        acao_add(conn, nome, meta, unid, cor)
        render_dashboard(conn)

    elif cmd == "rm" and len(args) >= 2:
        acao_rm(conn, int(args[1]))
        render_dashboard(conn)

    elif cmd == "json":
        estado = obter_estado_completo(conn)
        for h in estado["habits"]:
            del h["logs"]
        print(json.dumps(estado, ensure_ascii=False, indent=2))

    elif cmd == "serve":
        porta = int(args[1]) if len(args) >= 2 else 8000
        servidor = HTTPServer(("0.0.0.0", porta), PulseAPIHandler)
        print(f"\n  {c('pulse api', '1;32')} // rodando em http://0.0.0.0:{porta}")
        print(f"  {c('GET  /api/status', '2')}              -> Resumo JSON (KWGT / IA)")
        print(f"  {c('GET  /api/do?id=1&val=30', '2')}      -> Registra progresso via URL")
        print(f"  {c('POST /api/do | /set | /add', '2')}    -> Webhooks para Agentes de IA\n")
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            print(f"\n  {c('Servidor encerrado.', '2')}\n")

    elif cmd == "demo":
        popular_demo(conn)
        render_dashboard(conn)

    else:
        print(f"\n  {c('pulse', '1')} // comandos disponiveis:")
        print(f"  {c('pulse', '1;32')}                                  Mostra o painel no terminal")
        print(f"  {c('pulse do <id> [valor]', '1;32')}                  Soma valor hoje (ou conclui a meta)")
        print(f"  {c('pulse set <id> <valor>', '1;32')}                 Define o valor exato de hoje (0 limpa)")
        print(f"  {c('pulse add <nome> [meta] [unid] [cor]', '1;32')}   Cria nova rotina")
        print(f"  {c('pulse rm <id>', '1;32')}                          Remove uma rotina")
        print(f"  {c('pulse json', '1;32')}                             Exporta o estado atual em JSON")
        print(f"  {c('pulse serve [porta]', '1;32')}                    Inicia a API HTTP 24/7 (padrao: 8000)")
        print(f"  {c('pulse demo', '1;32')}                             Recarrega dados de demonstracao\n")

if __name__ == "__main__":
    main()
