import random
import shutil
import datetime

# Cores ANSI Nativas (100% adaptáveis ao tema do seu terminal)
def c(txt: str, codigos: str = "") -> str:
    if not codigos:
        return txt
    return f"\033[{codigos}m{txt}\033[0m"

# --- RESPONSIVIDADE E DATA DINÂMICA ---
hoje = datetime.datetime.now()
dias_semana = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

DATA_ATUAL = f"{dias_semana[hoje.weekday()]} {hoje.day} {meses[hoje.month - 1]}"
HOJE_IDX = hoje.weekday()  # 0 = Seg, 6 = Dom

PADDING = 4
MARGEM = " " * PADDING

largura_terminal = shutil.get_terminal_size((42, 20)).columns
espaco_util = largura_terminal - (PADDING * 2) - 4
SEMANAS = max(4, min(52, espaco_util // 2)) 
LARGURA_APP = 4 + (SEMANAS * 2)

def alinhar(esq_raw: str, esq_fmt: str, dir_raw: str, dir_fmt: str) -> str:
    espacos = max(1, LARGURA_APP - len(esq_raw) - len(dir_raw))
    return f"{MARGEM}{esq_fmt}{' ' * espacos}{dir_fmt}"

# --- PALETA BASEADA NO TEMA DO TERMINAL ---
# "1" = Negrito do tema, "2" = Cinza/Dim do tema
# As tarefas recebem os tons gerados nativamente: [Vazio, Fraco, Normal, Forte]
TAREFAS = [
    {
        "id": "01",
        "nome": "DEEP WORK",
        "status_esq": "2h15m / 2h00m hoje",
        "status_dir": "91% · 184h total",
        "streak": 18,
        "feita_hoje": True,
        "cor_base": "32", # Verde nativo
        "tons": ["2", "2;32", "32", "1;32"],
        "pesos": [0.08, 0.15, 0.42, 0.35],
    },
    {
        "id": "02",
        "nome": "ESTUDO DE EXATAS",
        "status_esq": "12/15 questoes",
        "status_dir": "[■■■■·] 80%",
        "streak": 6,
        "feita_hoje": True,
        "cor_base": "34", # Azul nativo
        "tons": ["2", "2;34", "34", "1;34"],
        "pesos": [0.22, 0.25, 0.33, 0.20],
    },
    {
        "id": "03",
        "nome": "TREINO DIARIO",
        "status_esq": "pendente · limite 20h",
        "status_dir": "[ ] hoje · 64%",
        "streak": 4,
        "feita_hoje": False,
        "cor_base": "33", # Amarelo/Laranja nativo
        "tons": ["2", "2;33", "33", "1;33"],
        "pesos": [0.36, 0.0, 0.0, 0.64],
    },
]

DIAS_LETRAS = ["s", "t", "q", "q", "s", "s", "d"]

print()

# --- CABEÇALHO DO APP ---
txt_esq_1 = "pulse"
txt_esq_2 = f" // {DATA_ATUAL}"
txt_dir = "2/3 concluidas"

esq_raw = txt_esq_1 + txt_esq_2
esq_fmt = f"{c(txt_esq_1, '1')}{c(txt_esq_2, '2')}"
dir_raw = txt_dir
dir_fmt = c(txt_dir, '2')

print(alinhar(esq_raw, esq_fmt, dir_raw, dir_fmt))

# Linha mais grossa (usando '━') adaptando as cores perfeitamente ao texto acima
espacos_meio = max(1, LARGURA_APP - len(esq_raw) - len(dir_raw))
linha_pulse  = c("━" * len(txt_esq_1), "1")
linha_data   = c("━" * len(txt_esq_2), "2")
linha_vazia  = c("━" * espacos_meio, "2")
linha_status = c("━" * len(dir_raw), "2")

print(f"{MARGEM}{linha_pulse}{linha_data}{linha_vazia}{linha_status}")
print()

# --- CORPO DO APP ---
for t in TAREFAS:
    cb = t["cor_base"]
    random.seed(t["id"])

    # Linha 1: Bloco Sólido + ID + Nome | Streak
    esq_1_raw = f"█ {t['id']}  {t['nome']}"
    esq_1_fmt = f"{c('█', cb)} {c(t['id'], f'1;{cb}')}  {c(t['nome'], '1')}"
    
    dir_1_raw = f"{t['streak']}d seq"
    dir_1_fmt = f"{c(str(t['streak']) + 'd', f'1;{cb}')} {c('seq', '2')}"
    print(alinhar(esq_1_raw, esq_1_fmt, dir_1_raw, dir_1_fmt))

    # Linha 2: Métrica | Resumo
    cor_status = f"1;{cb}" if t["feita_hoje"] else "2"
    print(alinhar(
        f"    {t['status_esq']}",
        f"    {c(t['status_esq'], cor_status)}",
        t["status_dir"],
        c(t["status_dir"], '2')
    ))

    # Grade dinâmica
    for dia_idx, letra in enumerate(DIAS_LETRAS):
        rotulo = c(letra, '2') if dia_idx in (0, 2, 4, 6) else " "
        blocos = []

        for sem in range(SEMANAS):
            ultima_semana = (sem == SEMANAS - 1)

            if ultima_semana and dia_idx > HOJE_IDX:
                # Dias futuros da semana atual (Ponto cinza/dim)
                blocos.append(c("·", "2"))
            elif ultima_semana and dia_idx == HOJE_IDX:
                # Dia atual
                nivel = 3 if t["feita_hoje"] else 0
                blocos.append(c("■", t["tons"][nivel]))
            else:
                # Histórico
                dias_atras = (SEMANAS - 1 - sem) * 7 + (HOJE_IDX - dia_idx)
                if 0 < dias_atras <= t["streak"]:
                    nivel = random.choice([2, 3]) if any(t["pesos"][1:3]) else 3
                else:
                    nivel = random.choices([0, 1, 2, 3], weights=t["pesos"])[0]
                blocos.append(c("■", t["tons"][nivel]))

        print(f"{MARGEM}{rotulo}  {' '.join(blocos)}")

    print()
