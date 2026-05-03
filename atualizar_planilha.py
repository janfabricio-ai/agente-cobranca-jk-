"""
Agente de Cobranca - Google Sheets
JK Artes Graficas

Abas:
  Dashboard   - KPIs + Aging + Top 10
  Consolidado - Todos inadimplentes (CRITICO > ALTO > MEDIO > ATENCAO) + Observacoes
  A Vencer    - Parcelas futuras
  Zenetti     - Detalhe raw Zenetti
  Mubys       - Detalhe raw Mubys
"""

import json
import os
from datetime import date

import gspread
from google.oauth2.service_account import Credentials
from gspread_formatting import (
    CellFormat, Color, TextFormat,
    format_cell_ranges, set_frozen, set_column_width, set_column_widths,
)

from processar_cobranca import (
    carregar_dados, formatar_moeda, formatar_data, DATA_HOJE
)

# ─────────────────────────────────────────
# CONFIGURACOES
# ─────────────────────────────────────────
BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
CREDENCIAIS_JSON = os.path.join(BASE_DIR, "credenciais_google.json")
DRIVE_IDS_JSON   = os.path.join(BASE_DIR, "drive_ids.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Paleta JK
COR_AZUL_ESC    = Color(0.114, 0.208, 0.380)
COR_AZUL_MED    = Color(0.157, 0.306, 0.502)
COR_AZUL_CLA    = Color(0.180, 0.459, 0.733)
COR_BRANCO      = Color(1, 1, 1)
COR_CINZA       = Color(0.949, 0.953, 0.961)
COR_VERM_ESC    = Color(0.698, 0.133, 0.133)
COR_VERM        = Color(0.929, 0.259, 0.212)
COR_LARANJA     = Color(0.957, 0.490, 0.102)
COR_AMARELO     = Color(0.988, 0.773, 0.145)
COR_VERDE       = Color(0.204, 0.659, 0.325)
COR_TEXTO_ESC   = Color(0.133, 0.133, 0.133)
COR_TEXTO_BRA   = Color(1, 1, 1)


# ─────────────────────────────────────────
# CONEXAO
# ─────────────────────────────────────────
def conectar():
    creds = Credentials.from_service_account_file(CREDENCIAIS_JSON, scopes=SCOPES)
    return gspread.authorize(creds)

def abrir_planilha(gc):
    with open(DRIVE_IDS_JSON) as f:
        ids = json.load(f)
    sh = gc.open_by_key(ids["planilha_id"])
    print(f"Planilha: {sh.url}")
    return sh

def garantir_aba(sh, nome, index=None):
    try:
        ws = sh.worksheet(nome)
        ws.clear()
        return ws
    except gspread.WorksheetNotFound:
        kwargs = {"rows": 500, "cols": 15}
        if index is not None:
            kwargs["index"] = index
        return sh.add_worksheet(title=nome, **kwargs)

def limpar_abas_extras(sh):
    esperadas = {"Dashboard", "Consolidado", "A Vencer", "Zenetti", "Mubys", "Historico"}
    for ws in sh.worksheets():
        if ws.title not in esperadas and ws.title == "Sheet1":
            try:
                sh.del_worksheet(ws)
            except Exception:
                pass


# ─────────────────────────────────────────
# HISTORICO (snapshot diario)
# ─────────────────────────────────────────
def gerenciar_historico(sh, resumo_v, resumo_av):
    """
    Garante a aba Historico (append-only). Grava snapshot do dia.
    Retorna dict com snapshot do dia anterior (ou None se primeiro dia).
    """
    print("  Historico...")
    try:
        ws = sh.worksheet("Historico")
        criada = False
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="Historico", rows=500, cols=8, index=5)
        ws.update(values=[["Data", "Vencido R$", "Vencido Qtd",
                           "A Vencer R$", "A Vencer Qtd", "Total R$",
                           "Top1 Cliente", "Top1 Valor"]], range_name="A1")
        format_cell_ranges(ws, [("A1:H1", fmt_header())])
        set_frozen(ws, rows=1)
        set_column_widths(ws, [(f"{c}:{c}", w) for c, w in
            [("A",110),("B",130),("C",110),("D",130),("E",110),("F",130),("G",260),("H",120)]])
        criada = True

    total_v  = sum(r['valor_total'] for r in resumo_v)
    total_av = sum(r['valor_total'] for r in resumo_av)
    top1     = resumo_v[0] if resumo_v else None
    hoje_str = DATA_HOJE.strftime('%Y-%m-%d')

    nova_linha = [
        hoje_str,
        round(total_v, 2),
        len(resumo_v),
        round(total_av, 2),
        len(resumo_av),
        round(total_v + total_av, 2),
        top1['cliente'] if top1 else '',
        round(top1['valor_total'], 2) if top1 else 0,
    ]

    linhas = ws.get_all_values()

    # Snapshot anterior (ultima linha que nao seja hoje)
    anterior = None
    for linha in reversed(linhas[1:]):
        if linha and linha[0] and linha[0] != hoje_str:
            try:
                anterior = {
                    'data': linha[0],
                    'vencido_total': float(linha[1] or 0),
                    'vencido_qtd': int(linha[2] or 0),
                    'a_vencer_total': float(linha[3] or 0),
                    'a_vencer_qtd': int(linha[4] or 0),
                }
            except (ValueError, IndexError):
                pass
            break

    # Atualiza linha de hoje se ja existe; senao append
    idx_hoje = None
    for i, linha in enumerate(linhas[1:], start=2):
        if linha and linha[0] == hoje_str:
            idx_hoje = i
            break

    if idx_hoje:
        ws.update(values=[nova_linha], range_name=f"A{idx_hoje}")
        print(f"    Snapshot do dia atualizado (linha {idx_hoje})")
    else:
        ws.append_row(nova_linha, value_input_option='USER_ENTERED')
        print(f"    Snapshot adicionado")

    return anterior


def gerenciar_snapshot_clientes(resumo_v):
    """
    Salva lista detalhada de clientes vencidos do dia em arquivo local.
    Retorna dict {cliente: valor} do dia anterior (ou None se primeiro dia).
    """
    snapshot_path = os.path.join(BASE_DIR, "snapshot_clientes.json")
    hoje_str = DATA_HOJE.strftime('%Y-%m-%d')

    historico = {}
    if os.path.exists(snapshot_path):
        try:
            with open(snapshot_path, encoding='utf-8') as f:
                historico = json.load(f)
        except (json.JSONDecodeError, OSError):
            historico = {}

    historico[hoje_str] = {
        r['cliente']: round(r['valor_total'], 2) for r in resumo_v
    }

    # Manter ultimos 60 dias
    datas = sorted(historico.keys())
    if len(datas) > 60:
        for d in datas[:-60]:
            del historico[d]

    with open(snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

    datas_anteriores = [d for d in sorted(historico.keys()) if d != hoje_str]
    if datas_anteriores:
        return historico[datas_anteriores[-1]]
    return None


# ─────────────────────────────────────────
# HELPERS DE FORMATACAO
# ─────────────────────────────────────────
def fmt_titulo(cor=None):
    return CellFormat(
        backgroundColor=cor or COR_AZUL_ESC,
        textFormat=TextFormat(bold=True, fontSize=12, foregroundColor=COR_TEXTO_BRA),
        horizontalAlignment="CENTER", verticalAlignment="MIDDLE",
    )

def fmt_header():
    return CellFormat(
        backgroundColor=COR_AZUL_MED,
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COR_TEXTO_BRA),
        horizontalAlignment="CENTER", verticalAlignment="MIDDLE",
    )

def fmt_kpi_label():
    return CellFormat(
        backgroundColor=COR_AZUL_CLA,
        textFormat=TextFormat(bold=True, fontSize=10, foregroundColor=COR_TEXTO_BRA),
        horizontalAlignment="CENTER", verticalAlignment="MIDDLE",
    )

def fmt_kpi_valor():
    return CellFormat(
        backgroundColor=COR_CINZA,
        textFormat=TextFormat(bold=True, fontSize=16, foregroundColor=COR_AZUL_ESC),
        horizontalAlignment="CENTER", verticalAlignment="MIDDLE",
    )

def fmt_normal(cor_fundo=None):
    return CellFormat(
        backgroundColor=cor_fundo or COR_BRANCO,
        textFormat=TextFormat(fontSize=10, foregroundColor=COR_TEXTO_ESC),
        verticalAlignment="MIDDLE",
    )

def cor_urgencia(dias):
    if dias > 90: return COR_VERM_ESC
    if dias > 60: return COR_VERM
    if dias > 30: return COR_LARANJA
    return COR_AMARELO

def label_urgencia(dias):
    if dias > 90: return "CRITICO"
    if dias > 60: return "ALTO"
    if dias > 30: return "MEDIO"
    return "ATENCAO"

def suavizar(cor, fator=0.12):
    return Color(
        cor.red   * fator + (1 - fator),
        cor.green * fator + (1 - fator),
        cor.blue  * fator + (1 - fator),
    )

def barra(valor, total, largura=20):
    if total == 0: return ""
    p = int((valor / total) * largura)
    return "█" * p + "░" * (largura - p)


# ─────────────────────────────────────────
# LER OBSERVACOES EXISTENTES
# ─────────────────────────────────────────
def ler_observacoes_existentes(sh):
    """
    Le a aba Consolidado antes de limpar e retorna dict {nome_cliente: observacao}.
    Preserva observacoes entre execucoes.
    """
    obs = {}
    try:
        ws = sh.worksheet("Consolidado")
        dados = ws.get_all_values()
        if len(dados) < 2:
            return obs
        header = [h.strip() for h in dados[0]]
        try:
            col_cliente = header.index("Cliente")
            col_obs = header.index("Observacoes")
        except ValueError:
            return obs
        for row in dados[1:]:
            if len(row) > max(col_cliente, col_obs):
                nome = row[col_cliente].strip()
                observacao = row[col_obs].strip()
                if nome and observacao:
                    obs[nome] = observacao
    except gspread.WorksheetNotFound:
        pass
    return obs


# ─────────────────────────────────────────
# ABA: DASHBOARD
# ─────────────────────────────────────────
def montar_dashboard(sh, resumo_v, resumo_av):
    print("  Dashboard...")
    ws = garantir_aba(sh, "Dashboard", index=0)

    hoje = DATA_HOJE.strftime('%d/%m/%Y')
    total_v   = sum(r['valor_total'] for r in resumo_v)
    total_av  = sum(r['valor_total'] for r in resumo_av)
    total_g   = total_v + total_av
    n_clientes = len(resumo_v)

    aging = {"0-30": {"c": 0, "v": 0.0}, "31-60": {"c": 0, "v": 0.0},
             "61-90": {"c": 0, "v": 0.0}, "90+":   {"c": 0, "v": 0.0}}
    for r in resumo_v:
        d = r['max_atraso']
        k = "0-30" if d <= 30 else "31-60" if d <= 60 else "61-90" if d <= 90 else "90+"
        aging[k]["c"] += 1
        aging[k]["v"] += r['valor_total']

    dados = [
        ["PAINEL DE COBRANCA - JK ARTES GRAFICAS", "", "", "", "", f"Atualizado: {hoje}"],
        [""],
        ["TOTAL VENCIDO", "", "TOTAL A VENCER", "", "TOTAL GERAL", ""],
        [formatar_moeda(total_v), "", formatar_moeda(total_av), "", formatar_moeda(total_g), ""],
        [""],
        ["CLIENTES INADIMPLENTES", "", "CRITICO (+90 dias)", "", "", ""],
        [str(n_clientes), "", formatar_moeda(aging["90+"]["v"]), "", "", ""],
        [""],
        ["AGING - FAIXAS DE ATRASO", "", "", "", "", ""],
        ["Faixa", "Clientes", "Valor em Aberto", "% do Total", "Representacao", ""],
    ]

    for faixa, info in aging.items():
        pct = (info['v'] / total_v * 100) if total_v else 0
        dados.append([f"{faixa} dias", info['c'], formatar_moeda(info['v']),
                      f"{pct:.1f}%", barra(info['v'], total_v), ""])

    dados += [
        [""],
        ["TOP 10 MAIORES DEVEDORES", "", "", "", "", ""],
        ["#", "Cliente", "Valor Total", "Parcelas", "Maior Atraso", "Urgencia"],
    ]
    for i, r in enumerate(resumo_v[:10], 1):
        dados.append([i, r['cliente'], formatar_moeda(r['valor_total']),
                      r['parcelas'], f"{r['max_atraso']} dias", label_urgencia(r['max_atraso'])])

    dados += [
        [""],
        ["PROXIMOS VENCIMENTOS (TOP 5)", "", "", "", "", ""],
        ["Cliente", "Valor", "Venc. Mais Proximo", "Parcelas", "Sistemas", ""],
    ]
    for r in resumo_av[:5]:
        dados.append([r['cliente'], formatar_moeda(r['valor_total']),
                      formatar_data(r['mais_proxima']), r['parcelas'], r['sistemas'], ""])

    ws.update(values=dados, range_name="A1")

    fmt = [
        ("A1:E1", fmt_titulo()),
        ("A3:B3", fmt_kpi_label()), ("C3:D3", fmt_kpi_label()), ("E3:F3", fmt_kpi_label()),
        ("A4:B4", fmt_kpi_valor()), ("C4:D4", fmt_kpi_valor()), ("E4:F4", fmt_kpi_valor()),
        ("A6:B6", fmt_kpi_label()), ("C6:D6", fmt_kpi_label()),
        ("A7:B7", fmt_kpi_valor()), ("C7:D7", fmt_kpi_valor()),
        ("A9:F9", fmt_titulo(COR_AZUL_MED)),
        ("A10:F10", fmt_header()),
        ("A13:F13", fmt_titulo(COR_AZUL_MED)),
        ("A14:F14", fmt_header()),
        ("A26:F26", fmt_titulo(COR_AZUL_MED)),
        ("A27:F27", fmt_header()),
    ]
    cores_aging = [COR_AMARELO, COR_LARANJA, COR_VERM, COR_VERM_ESC]
    for i, cor in enumerate(cores_aging):
        fmt.append((f"A{11+i}:F{11+i}", CellFormat(backgroundColor=suavizar(cor, 0.3),
                                                    textFormat=TextFormat(fontSize=10, bold=(i==3)))))
    for i, r in enumerate(resumo_v[:10]):
        row = 15 + i
        cor = cor_urgencia(r['max_atraso'])
        fmt.append((f"A{row}:E{row}", CellFormat(backgroundColor=suavizar(cor),
                                                  textFormat=TextFormat(fontSize=10))))
        fmt.append((f"F{row}", CellFormat(backgroundColor=cor,
                                          textFormat=TextFormat(bold=True, fontSize=9,
                                                                foregroundColor=COR_TEXTO_BRA),
                                          horizontalAlignment="CENTER")))
    format_cell_ranges(ws, fmt)

    for merge in ["A1:E1", "A3:B3", "C3:D3", "E3:F3",
                  "A4:B4", "C4:D4", "E4:F4",
                  "A6:B6", "C6:D6", "A7:B7", "C7:D7",
                  "A9:F9", "A13:F13", "A26:F26"]:
        try: ws.merge_cells(merge)
        except Exception: pass

    set_frozen(ws, rows=1)
    set_column_widths(ws, [(f"{c}:{c}", w) for c, w in
        [("A",280),("B",100),("C",160),("D",90),("E",170),("F",100)]])


# ─────────────────────────────────────────
# ABA: CONSOLIDADO
# ─────────────────────────────────────────
def montar_consolidado(sh, resumo, observacoes_antigas):
    print("  Consolidado...")
    ws = garantir_aba(sh, "Consolidado", index=1)

    header = ["Cliente", "Telefone", "Valor Total", "Parcelas", "Sistemas",
              "Venc. Mais Antigo", "Maior Atraso (dias)", "Urgencia", "Observacoes"]

    linhas = [header]
    for r in resumo:
        # Recupera observacao antiga se existir
        obs = observacoes_antigas.get(r['cliente'], '')
        linhas.append([
            r['cliente'],
            r.get('telefone', ''),
            formatar_moeda(r['valor_total']),
            r['parcelas'],
            r['sistemas'],
            formatar_data(r['mais_antiga']),
            r['max_atraso'],
            label_urgencia(r['max_atraso']),
            obs,
        ])

    ws.update(values=linhas, range_name="A1")

    fmt = [("A1:I1", fmt_header())]
    for i, r in enumerate(resumo):
        row = i + 2
        cor = cor_urgencia(r['max_atraso'])
        cor_bg = suavizar(cor) if row % 2 == 0 else COR_BRANCO
        fmt.append((f"A{row}:H{row}", fmt_normal(cor_bg)))
        fmt.append((f"H{row}", CellFormat(backgroundColor=cor,
                                          textFormat=TextFormat(bold=True, fontSize=9,
                                                                foregroundColor=COR_TEXTO_BRA),
                                          horizontalAlignment="CENTER")))
        # Coluna Observacoes: fundo levemente diferente para destaque
        fmt.append((f"I{row}", CellFormat(
            backgroundColor=Color(0.980, 0.980, 0.902),
            textFormat=TextFormat(fontSize=10, foregroundColor=COR_TEXTO_ESC),
        )))

    format_cell_ranges(ws, fmt)
    set_frozen(ws, rows=1)

    set_column_widths(ws, [(f"{c}:{c}", w) for c, w in
        [("A",260),("B",140),("C",130),("D",75),
         ("E",130),("F",130),("G",150),("H",90),("I",300)]])


# ─────────────────────────────────────────
# ABA: A VENCER
# ─────────────────────────────────────────
def montar_a_vencer(sh, resumo_av):
    print("  A Vencer...")
    ws = garantir_aba(sh, "A Vencer", index=2)

    total = sum(r['valor_total'] for r in resumo_av)
    header_titulo = [f"CONTAS A VENCER - {DATA_HOJE.strftime('%d/%m/%Y')} | "
                     f"Total: {formatar_moeda(total)} | {len(resumo_av)} clientes",
                     "", "", "", "", ""]
    header = ["Cliente", "Telefone", "Valor Total", "Parcelas",
              "Venc. Mais Proximo", "Sistemas"]

    linhas = [header_titulo, header]
    for r in resumo_av:
        linhas.append([
            r['cliente'],
            r.get('telefone', ''),
            formatar_moeda(r['valor_total']),
            r['parcelas'],
            formatar_data(r['mais_proxima']),
            r['sistemas'],
        ])

    ws.update(values=linhas, range_name="A1")

    fmt = [
        ("A1:F1", fmt_titulo(COR_VERDE)),
        ("A2:F2", fmt_header()),
    ]
    for i in range(len(resumo_av)):
        row = i + 3
        cor_bg = COR_CINZA if row % 2 == 0 else COR_BRANCO
        fmt.append((f"A{row}:F{row}", fmt_normal(cor_bg)))

    format_cell_ranges(ws, fmt)
    try: ws.merge_cells("A1:F1")
    except Exception: pass
    set_frozen(ws, rows=2)

    set_column_widths(ws, [(f"{c}:{c}", w) for c, w in
        [("A",260),("B",140),("C",130),("D",75),("E",130),("F",130)]])


# ─────────────────────────────────────────
# ABA: ZENETTI
# ─────────────────────────────────────────
def montar_zenetti(sh, registros):
    print("  Zenetti...")
    ws = garantir_aba(sh, "Zenetti", index=3)
    header = ["Documento", "Cliente", "Vencimento", "Valor", "Atraso (dias)"]
    linhas = [header]
    for r in sorted(registros, key=lambda x: x['atraso_dias'], reverse=True):
        linhas.append([r['documento'], r['cliente'], formatar_data(r['vencimento']),
                       formatar_moeda(r['valor']), r['atraso_dias']])
    ws.update(values=linhas, range_name="A1")
    fmt = [("A1:E1", fmt_header())]
    for i, r in enumerate(registros):
        row = i + 2
        cor = cor_urgencia(r['atraso_dias'])
        fmt.append((f"A{row}:E{row}", fmt_normal(suavizar(cor) if row%2==0 else COR_BRANCO)))
    format_cell_ranges(ws, fmt)
    set_frozen(ws, rows=1)
    set_column_widths(ws, [(f"{c}:{c}", w) for c, w in
        [("A",150),("B",250),("C",120),("D",120),("E",130)]])


# ─────────────────────────────────────────
# ABA: MUBYS
# ─────────────────────────────────────────
def montar_mubys(sh, registros):
    print("  Mubys...")
    ws = garantir_aba(sh, "Mubys", index=4)
    header = ["Nota Fiscal", "Cliente", "Vencimento", "Valor Atualizado", "Atraso (dias)", "Contato"]
    linhas = [header]
    for r in sorted(registros, key=lambda x: x['atraso_dias'], reverse=True):
        linhas.append([r['documento'], r['cliente'], formatar_data(r['vencimento']),
                       formatar_moeda(r['valor']), r['atraso_dias'], r.get('contato','')])
    ws.update(values=linhas, range_name="A1")
    fmt = [("A1:F1", fmt_header())]
    for i, r in enumerate(registros):
        row = i + 2
        cor = cor_urgencia(r['atraso_dias'])
        fmt.append((f"A{row}:F{row}", fmt_normal(suavizar(cor) if row%2==0 else COR_BRANCO)))
    format_cell_ranges(ws, fmt)
    set_frozen(ws, rows=1)
    set_column_widths(ws, [(f"{c}:{c}", w) for c, w in
        [("A",130),("B",280),("C",120),("D",140),("E",130),("F",300)]])


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    print("=" * 60)
    print("  AGENTE DE COBRANCA - GOOGLE SHEETS")
    print("=" * 60)

    # Carregar dados do Drive
    resumo_v, resumo_av, zen, mub = carregar_dados()

    # Conectar planilha
    print("\nConectando ao Google Sheets...")
    gc = conectar()
    sh = abrir_planilha(gc)

    # Ler observacoes antes de limpar
    print("Preservando observacoes existentes...")
    obs_antigas = ler_observacoes_existentes(sh)
    print(f"  {len(obs_antigas)} observacoes preservadas")

    limpar_abas_extras(sh)

    # Montar abas
    print("\nAtualizando abas...")
    montar_dashboard(sh, resumo_v, resumo_av)
    montar_consolidado(sh, resumo_v, obs_antigas)
    montar_a_vencer(sh, resumo_av)
    montar_zenetti(sh, zen)
    montar_mubys(sh, mub)

    # Historico (snapshot diario para comparativos)
    snapshot_anterior     = gerenciar_historico(sh, resumo_v, resumo_av)
    clientes_ontem        = gerenciar_snapshot_clientes(resumo_v)

    total_v  = sum(r['valor_total'] for r in resumo_v)
    total_av = sum(r['valor_total'] for r in resumo_av)

    print("\n" + "=" * 60)
    print("  PLANILHA ATUALIZADA!")
    print("=" * 60)
    print(f"  Inadimplentes:  {len(resumo_v)} clientes | {formatar_moeda(total_v)}")
    print(f"  A vencer:       {len(resumo_av)} clientes | {formatar_moeda(total_av)}")
    print(f"  Total geral:    {formatar_moeda(total_v + total_av)}")
    print(f"  Observacoes mantidas: {len(obs_antigas)}")
    if snapshot_anterior:
        delta_v = total_v - snapshot_anterior['vencido_total']
        sinal = '+' if delta_v >= 0 else ''
        print(f"  vs. {snapshot_anterior['data']}: vencido {sinal}{formatar_moeda(delta_v)}")
    print(f"\n  URL: {sh.url}")

    return {
        'resumo_v': resumo_v,
        'resumo_av': resumo_av,
        'zen': zen,
        'mub': mub,
        'total_v': total_v,
        'total_av': total_av,
        'snapshot_anterior': snapshot_anterior,
        'clientes_ontem': clientes_ontem,
        'planilha_url': sh.url,
    }


if __name__ == "__main__":
    main()
