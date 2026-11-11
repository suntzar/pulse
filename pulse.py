#!/usr/bin/env python3
import sys
import os
import sqlite3
import shutil
import datetime
import random
from pathlib import Path

# Banco de dados salvo na sua home para funcionar de qualquer diretório
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

# --- BANCO DE DADOS (SQLITE NATIVO) ---
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

# --- REGRAS DE NEGÓCIO E MÉTRICAS ---
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
    # Se hoje já tem registro, conta a partir de hoje; senão, verifica a partir de ontem
    cursor = hoje if logs_map.get(hoje.isoformat(), 0) > 0 else hoje - datetime.timedelta(days=1)
    while logs_map.get(cursor.isoformat(), 0) > 0:
        streak += 1
        cursor -= datetime.timedelta(days=1)
    return streak

def formatar_status(val_hoje: float, goal: float, unit: str, rate: int, total_val: float) -> tuple[str, str]:
    if unit == "min":
        esq = f"{formatar_tempo(val_hoje)} / {formatar_tempo(goal)} hoje"
        dir_s = f"{rate}% · { int(total_val // 60) }h total"
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

# --- RENDERIZAÇÃO DO DASHBOARD ---
def render_dashboard(conn: sqlite3.Connection):
    habits = conn.execute("SELECT * FROM habits ORDER BY id ASC").fetchall()
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

    PADDING = 4
    MARGEM = " " * PADDING
    largura_terminal = shutil.get_terminal_size((42, 20)).columns
    espaco_util = largura_terminal - (PADDING * 2) - 4
    SEMANAS = max(4, min(52, espaco_util // 2))
    LARGURA_APP = 4 + (SEMANAS * 2)

    def alinhar(esq_raw: str, esq_fmt: str, dir_raw: str, dir_fmt: str) -> str:
        espacos = max(1, LARGURA_APP - len(esq_raw) - len(dir_raw))
        return f"{MARGEM}{esq_fmt}{' ' * espacos}{dir_fmt}"

    # Carrega logs de todas as tarefas
    logs_por_habito = {}
    concluidas_hoje = 0
    hoje_iso = hoje.isoformat()

    for h in habits:
        rows = conn.execute("SELECT date, value FROM logs WHERE habit_id = ?", (h["id"],)).fetchall()
        mapa = {r["date"]: r["value"] for r in rows}
        logs_por_habito[h["id"]] = mapa
        if mapa.get(hoje_iso, 0) >= h["goal"]:
            concluidas_hoje += 1

    print()
    # Cabeçalho
    txt_esq_1 = "pulse"
    txt_esq_2 = f" // {data_atual}"
    txt_dir = f"{concluidas_hoje}/{len(habits)} concluidas"

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
    total_dias_visiveis = ((SEMANAS - 1) * 7) + (hoje_idx + 1)

    for idx_ordem, h in enumerate(habits, start=1):
        cb = CORES.get(h["color"], "32")
        tons = ["2", f"2;{cb}", cb, f"1;{cb}"]
        mapa = logs_por_habito[h["id"]]

        val_hoje = mapa.get(hoje_iso, 0.0)
        feita_hoje = val_hoje > 0
        streak = calcular_streak(mapa, hoje)

        # Consistência nos dias visíveis na grade
        dias_ativos = 0
        for d in range(total_dias_visiveis):
            dt_iso = (hoje - datetime.timedelta(days=d)).isoformat()
            if mapa.get(dt_iso, 0) > 0:
                dias_ativos += 1
        rate = int(round((dias_ativos / max(1, total_dias_visiveis)) * 100))
        total_val = sum(mapa.values())

        id_str = f"{h['id']:02d}"
        nome_upper = h["name"].upper()

        # Linha 1: █ ID  NOME | Streak
        esq_1_raw = f"█ {id_str}  {nome_upper}"
        esq_1_fmt = f"{c('█', cb)} {c(id_str, f'1;{cb}')}  {c(nome_upper, '1')}"
        dir_1_raw = f"{streak}d seq"
        dir_1_fmt = f"{c(f'{streak}d', f'1;{cb}')} {c('seq', '2')}"
        print(alinhar(esq_1_raw, esq_1_fmt, dir_1_raw, dir_1_fmt))

        # Linha 2: Status Esquerda | Status Direita
        status_esq, status_dir = formatar_status(val_hoje, h["goal"], h["unit"], rate, total_val)
        cor_status = f"1;{cb}" if feita_hoje else "2"
        print(alinhar(f"    {status_esq}", f"    {c(status_esq, cor_status)}", status_dir, c(status_dir, "2")))

        # Grade 7xSEMANAS baseada no calendário real
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

# --- COMANDOS DO CLI ---
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
        cur = conn.execute(
            "INSERT INTO habits (name, goal, unit, color) VALUES (?, ?, ?, ?)",
            (nome, meta, unid, cor),
        )
        h_id = cur.lastrowid
        random.seed(h_id)

        for d in range(1, 365):
            dt = (hoje - datetime.timedelta(days=d)).isoformat()
            if d <= streak:
                lvl = random.choice([2, 3]) if unid != "check" else 3
            else:
                lvl = random.choices([0, 1, 2, 3], weights=pesos)[0]

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
    hoje_iso = datetime.date.today().isoformat()

    if cmd in ("do", "check", "c") and len(args) >= 2:
        h_id = int(args[1])
        habit = conn.execute("SELECT * FROM habits WHERE id = ?", (h_id,)).fetchone()
        if not habit:
            print(c(f"  Erro: Tarefa {h_id:02d} nao encontrada.", "31"))
            return
        # Se passar valor (ex: pulse do 1 45), soma ao dia de hoje; se não passar, bate a meta
        atual = conn.execute("SELECT value FROM logs WHERE habit_id = ? AND date = ?", (h_id, hoje_iso)).fetchone()
        val_atual = atual["value"] if atual else 0.0
        novo_val = (val_atual + float(args[2])) if len(args) >= 3 else habit["goal"]

        conn.execute("INSERT OR REPLACE INTO logs (habit_id, date, value) VALUES (?, ?, ?)", (h_id, hoje_iso, novo_val))
        conn.commit()
        render_dashboard(conn)

    elif cmd == "set" and len(args) >= 3:
        h_id, val = int(args[1]), float(args[2])
        if val <= 0:
            conn.execute("DELETE FROM logs WHERE habit_id = ? AND date = ?", (h_id, hoje_iso))
        else:
            conn.execute("INSERT OR REPLACE INTO logs (habit_id, date, value) VALUES (?, ?, ?)", (h_id, hoje_iso, val))
        conn.commit()
        render_dashboard(conn)

    elif cmd == "add" and len(args) >= 2:
        nome = args[1]
        meta = float(args[2]) if len(args) >= 3 else 1.0
        unid = args[3].lower() if len(args) >= 4 else "check"
        cor = args[4].lower() if len(args) >= 5 else "verde"
        conn.execute("INSERT INTO habits (name, goal, unit, color) VALUES (?, ?, ?, ?)", (nome, meta, unid, cor))
        conn.commit()
        render_dashboard(conn)

    elif cmd == "rm" and len(args) >= 2:
        h_id = int(args[1])
        conn.execute("DELETE FROM logs WHERE habit_id = ?", (h_id,))
        conn.execute("DELETE FROM habits WHERE id = ?", (h_id,))
        conn.commit()
        render_dashboard(conn)

    elif cmd == "demo":
        popular_demo(conn)
        render_dashboard(conn)

    else:
        print(f"\n  {c('pulse', '1')} // comandos disponiveis:")
        print(f"  {c('pulse', '1;32')}                                  Mostra o painel")
        print(f"  {c('pulse do <id> [valor]', '1;32')}                  Soma valor hoje (ou conclui a meta se omitido)")
        print(f"  {c('pulse set <id> <valor>', '1;32')}                 Define o valor exato de hoje (0 para limpar)")
        print(f"  {c('pulse add <nome> [meta] [unid] [cor]', '1;32')}   Cria tarefa (unid: min, check, questoes...)")
        print(f"  {c('pulse rm <id>', '1;32')}                          Remove uma tarefa")
        print(f"  {c('pulse demo', '1;32')}                             Carrega as 3 tarefas de exemplo com historico\n")

if __name__ == "__main__":
    main()
