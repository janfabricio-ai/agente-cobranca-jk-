"""
Gerador do PDF executivo de Cobranca - JK Artes Graficas.
4 paginas: (1) Resumo+Analise, (2) Recebimento Futuro, (3) Top 20, (4) Lista Completa.
"""

import os
from datetime import date, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PDFS_DIR  = os.path.join(BASE_DIR, "pdfs")
os.makedirs(PDFS_DIR, exist_ok=True)

# Paleta JK
AZUL_ESC = colors.HexColor("#1D356E")
AZUL_MED = colors.HexColor("#284EA0")
AZUL_CLA = colors.HexColor("#2E75BB")
VERM     = colors.HexColor("#B22222")
LARANJA  = colors.HexColor("#F47D1A")
AMARELO  = colors.HexColor("#FCC525")
VERDE    = colors.HexColor("#34A853")
CINZA_C  = colors.HexColor("#F2F4F6")
CINZA_M  = colors.HexColor("#9AA3AD")
PRETO    = colors.HexColor("#222222")


def fm(v):
    return f"R$ {v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def cor_atraso(dias):
    if dias > 90:  return VERM
    if dias > 60:  return LARANJA
    if dias > 30:  return AMARELO
    return VERDE


def cor_alerta(nivel):
    return {
        'critico':  VERM,
        'alto':     LARANJA,
        'medio':    AMARELO,
        'positivo': VERDE,
    }.get(nivel, AZUL_MED)


def make_styles():
    base = getSampleStyleSheet()
    s = {
        'titulo':     ParagraphStyle('titulo', parent=base['Heading1'],
                                     fontSize=18, textColor=AZUL_ESC, spaceAfter=4,
                                     fontName='Helvetica-Bold'),
        'subtitulo':  ParagraphStyle('subtitulo', parent=base['Normal'],
                                     fontSize=10, textColor=CINZA_M, spaceAfter=14),
        'h2':         ParagraphStyle('h2', parent=base['Heading2'],
                                     fontSize=13, textColor=AZUL_MED, spaceBefore=8,
                                     spaceAfter=6, fontName='Helvetica-Bold'),
        'h3':         ParagraphStyle('h3', parent=base['Heading3'],
                                     fontSize=11, textColor=AZUL_ESC,
                                     spaceBefore=4, spaceAfter=2,
                                     fontName='Helvetica-Bold'),
        'normal':     ParagraphStyle('normal', parent=base['Normal'],
                                     fontSize=9, textColor=PRETO, leading=12),
        'pequeno':    ParagraphStyle('pequeno', parent=base['Normal'],
                                     fontSize=8, textColor=PRETO, leading=10),
        'kpi_label':  ParagraphStyle('kpi_label', parent=base['Normal'],
                                     fontSize=8, textColor=CINZA_M,
                                     alignment=TA_CENTER),
        'kpi_valor':  ParagraphStyle('kpi_valor', parent=base['Normal'],
                                     fontSize=15, textColor=AZUL_ESC,
                                     fontName='Helvetica-Bold', alignment=TA_CENTER),
        'kpi_delta':  ParagraphStyle('kpi_delta', parent=base['Normal'],
                                     fontSize=8, alignment=TA_CENTER),
        'alerta_t':   ParagraphStyle('alerta_t', parent=base['Normal'],
                                     fontSize=10, textColor=colors.white,
                                     fontName='Helvetica-Bold', leading=13),
        'alerta_d':   ParagraphStyle('alerta_d', parent=base['Normal'],
                                     fontSize=9, textColor=PRETO, leading=12),
    }
    return s


# ─────────────────────────────────────────
# PAGINA 1 - RESUMO EXECUTIVO + ANALISE
# ─────────────────────────────────────────
def pagina_resumo(story, st, dados, analise):
    hoje = date.today()
    total_v   = dados['total_v']
    total_av  = dados['total_av']
    qtd_v     = len(dados['resumo_v'])
    qtd_av    = len(dados['resumo_av'])
    comp      = analise['comparativo']

    # Cabecalho
    story.append(Paragraph("Relatorio de Cobranca - JK Artes Graficas", st['titulo']))
    story.append(Paragraph(f"Posicao em {hoje.strftime('%d/%m/%Y')} - "
                           f"gerado automaticamente", st['subtitulo']))

    # KPIs principais (4 colunas)
    def kpi_cell(label, valor, delta_txt=None, delta_cor=None):
        cell = [Paragraph(label, st['kpi_label']),
                Paragraph(valor, st['kpi_valor'])]
        if delta_txt:
            cor = delta_cor or CINZA_M
            cell.append(Paragraph(f'<font color="{cor.hexval()}">{delta_txt}</font>',
                                  st['kpi_delta']))
        return cell

    delta_v_txt = delta_av_txt = None
    delta_v_cor = delta_av_cor = None
    if comp:
        sinal_v  = '+' if comp['delta_v_abs'] >= 0 else ''
        sinal_av = '+' if comp['delta_av_abs'] >= 0 else ''
        delta_v_txt  = f"{sinal_v}{fm(comp['delta_v_abs'])} ({comp['delta_v_pct']:+.1f}%)"
        delta_av_txt = f"{sinal_av}{fm(comp['delta_av_abs'])} ({comp['delta_av_pct']:+.1f}%)"
        delta_v_cor  = VERM if comp['delta_v_abs'] > 0 else VERDE
        delta_av_cor = VERDE if comp['delta_av_abs'] > 0 else VERM

    kpi_data = [[
        kpi_cell("VENCIDO", fm(total_v), delta_v_txt, delta_v_cor),
        kpi_cell("A VENCER", fm(total_av), delta_av_txt, delta_av_cor),
        kpi_cell("TOTAL GERAL", fm(total_v + total_av)),
        kpi_cell("CLIENTES INADIMP.", str(qtd_v),
                 f"{comp['delta_qtd_v']:+d} vs ontem" if comp else None,
                 VERM if comp and comp['delta_qtd_v'] > 0 else VERDE),
    ]]
    kpi_table = Table(kpi_data, colWidths=[4.2*cm]*4, rowHeights=[2.4*cm])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CINZA_C),
        ('BOX',        (0,0), (-1,-1), 0.5, CINZA_M),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.white),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.4*cm))

    # ANALISE DO DIA - bloco em destaque
    story.append(Paragraph("Analise do dia", st['h2']))

    # Heuristicas resumo (1 paragrafo)
    aging = analise['aging']
    conc  = analise['concentracao']
    bn    = analise['bola_neve']

    resumo_txt = (
        f"<b>Concentracao:</b> os 5 maiores devedores somam "
        f"<b>{fm(conc['valor_top'])}</b> ({conc['pct_top']:.0f}% do vencido). "
        f"<b>Aging:</b> {aging['90+']['qtd']} cliente(s) acima de 90 dias = "
        f"<b>{fm(aging['90+']['valor'])}</b> ({aging['90+']['pct']:.0f}% do total) - "
        f"janela legal para protesto. "
    )
    if bn:
        resumo_txt += (f"<b>Bola de neve:</b> {len(bn)} cliente(s) ja vencidos com "
                       f"nova parcela em 7 dias - confirmar pagamento antes de virar "
                       f"divida nova.")
    story.append(Paragraph(resumo_txt, st['normal']))
    story.append(Spacer(1, 0.3*cm))

    # Alertas em caixas coloridas
    for al in analise['alertas']:
        cor = cor_alerta(al['nivel'])
        cab = Table([[Paragraph(f"[{al['nivel'].upper()}] {al['titulo']}",
                                 st['alerta_t'])]],
                    colWidths=[17*cm])
        cab.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), cor),
            ('LEFTPADDING',(0,0), (-1,-1), 6),
            ('RIGHTPADDING',(0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ]))
        det = Table([[Paragraph(al['detalhe'], st['alerta_d'])]],
                    colWidths=[17*cm])
        det.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), CINZA_C),
            ('LEFTPADDING',(0,0), (-1,-1), 6),
            ('RIGHTPADDING',(0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING',(0,0),(-1,-1), 4),
            ('LINEBELOW',  (0,0), (-1,-1), 0.3, CINZA_M),
        ]))
        story.append(KeepTogether([cab, det, Spacer(1, 0.2*cm)]))

    story.append(Spacer(1, 0.2*cm))

    # AGING - tabela compacta
    story.append(Paragraph("Aging dos vencidos", st['h2']))
    aging_data = [["Faixa", "Clientes", "Valor", "% do total"]]
    for faixa in ['0-30', '31-60', '61-90', '90+']:
        a = aging[faixa]
        aging_data.append([f"{faixa} dias", str(a['qtd']),
                           fm(a['valor']), f"{a['pct']:.1f}%"])
    aging_table = Table(aging_data, colWidths=[3*cm, 2.5*cm, 4*cm, 3*cm])
    aging_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AZUL_ESC),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 9),
        ('GRID',       (0,0), (-1,-1), 0.3, CINZA_M),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (1,0), (-1,-1), 'RIGHT'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING',(0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_C]),
        # cor da faixa de 90+
        ('TEXTCOLOR',  (0,4), (0,4), VERM),
        ('FONTNAME',   (0,4), (-1,4), 'Helvetica-Bold'),
    ]))
    story.append(aging_table)

    # Estrategias top 5
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Acoes recomendadas (Top 5)", st['h2']))
    estrat_data = [["#", "Cliente", "Valor", "Atraso", "Acao recomendada"]]
    for i, e in enumerate(analise['estrategias'], 1):
        estrat_data.append([
            str(i),
            e['cliente'][:38],
            fm(e['valor']),
            f"{e['atraso']} d",
            e['acao'],
        ])
    estrat_table = Table(estrat_data,
                         colWidths=[0.8*cm, 5.5*cm, 2.5*cm, 1.5*cm, 7*cm])
    estrat_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AZUL_ESC),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 8.5),
        ('GRID',       (0,0), (-1,-1), 0.3, CINZA_M),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (2,1), (3,-1), 'RIGHT'),
        ('ALIGN',      (0,0), (0,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING',(0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_C]),
    ]))
    story.append(estrat_table)


# ─────────────────────────────────────────
# PAGINA 2 - RECEBIMENTO FUTURO
# ─────────────────────────────────────────
def pagina_recebimento(story, st, dados, analise):
    hoje = date.today()
    story.append(PageBreak())
    story.append(Paragraph("Projecao de Recebimento", st['titulo']))
    story.append(Paragraph(f"Base para fluxo de caixa - {hoje.strftime('%d/%m/%Y')}",
                           st['subtitulo']))

    # KPIs de janela
    proj = analise['projecao']
    kpi_data = [[
        Paragraph("PROXIMOS 7 DIAS", st['kpi_label']),
        Paragraph("PROXIMOS 15 DIAS", st['kpi_label']),
        Paragraph("PROXIMOS 30 DIAS", st['kpi_label']),
        Paragraph("PROXIMOS 60 DIAS", st['kpi_label']),
    ], [
        Paragraph(fm(proj['7d']['valor']),  st['kpi_valor']),
        Paragraph(fm(proj['15d']['valor']), st['kpi_valor']),
        Paragraph(fm(proj['30d']['valor']), st['kpi_valor']),
        Paragraph(fm(proj['60d']['valor']), st['kpi_valor']),
    ], [
        Paragraph(f"{proj['7d']['qtd_clientes']} clientes",  st['kpi_delta']),
        Paragraph(f"{proj['15d']['qtd_clientes']} clientes", st['kpi_delta']),
        Paragraph(f"{proj['30d']['qtd_clientes']} clientes", st['kpi_delta']),
        Paragraph(f"{proj['60d']['qtd_clientes']} clientes", st['kpi_delta']),
    ]]
    kpi_table = Table(kpi_data, colWidths=[4.2*cm]*4)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), CINZA_C),
        ('BOX',        (0,0), (-1,-1), 0.5, CINZA_M),
        ('GRID',       (0,0), (-1,-1), 0.5, colors.white),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.5*cm))

    # CALENDARIO DIARIO (proximos 14 dias)
    story.append(Paragraph("Calendario diario - proximos 14 dias", st['h2']))
    cal = analise['calendario']
    max_v = max((d['valor'] for d in cal), default=1) or 1

    cal_data = [["Dia", "Data", "Parcelas", "Valor", "Visualizacao"]]
    dias_pt = ['Seg','Ter','Qua','Qui','Sex','Sab','Dom']
    for d in cal[:14]:
        weekday = dias_pt[d['data'].weekday()]
        bar_len = int((d['valor'] / max_v) * 30) if d['valor'] else 0
        bar = '█' * bar_len
        cal_data.append([
            weekday,
            d['data'].strftime('%d/%m'),
            str(d['qtd']) if d['qtd'] else '-',
            fm(d['valor']) if d['valor'] else '-',
            bar,
        ])
    cal_table = Table(cal_data,
                      colWidths=[1.5*cm, 1.8*cm, 2*cm, 3*cm, 8.5*cm])
    cal_style = [
        ('BACKGROUND', (0,0), (-1,0), AZUL_ESC),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 8.5),
        ('GRID',       (0,0), (-1,-1), 0.3, CINZA_M),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (2,0), (3,-1), 'RIGHT'),
        ('ALIGN',      (0,0), (1,-1), 'CENTER'),
        ('TEXTCOLOR',  (4,1), (4,-1), AZUL_CLA),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING',(0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_C]),
    ]
    # Destacar fins de semana
    for i, d in enumerate(cal[:14], 1):
        if d['data'].weekday() >= 5:
            cal_style.append(('TEXTCOLOR', (0,i), (1,i), CINZA_M))
    cal_table.setStyle(TableStyle(cal_style))
    story.append(cal_table)
    story.append(Spacer(1, 0.4*cm))

    # TOP 20 RECEBIMENTOS ESPERADOS
    story.append(Paragraph("Top 20 maiores recebimentos esperados", st['h2']))
    av_ord = sorted(dados['resumo_av'], key=lambda x: -x['valor_total'])[:20]
    top_data = [["#", "Cliente", "Valor", "Parcelas", "Mais proxima"]]
    for i, r in enumerate(av_ord, 1):
        proxi = r.get('mais_proxima')
        top_data.append([
            str(i),
            r['cliente'][:42],
            fm(r['valor_total']),
            str(r.get('parcelas', 0)),
            proxi.strftime('%d/%m/%Y') if proxi else '-',
        ])
    top_table = Table(top_data,
                      colWidths=[0.8*cm, 7.5*cm, 3*cm, 2*cm, 3.5*cm])
    top_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), AZUL_ESC),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 8.5),
        ('GRID',       (0,0), (-1,-1), 0.3, CINZA_M),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (2,0), (-1,-1), 'RIGHT'),
        ('ALIGN',      (0,0), (0,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING',(0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_C]),
    ]))
    story.append(top_table)


# ─────────────────────────────────────────
# PAGINA 3 - TOP 20 INADIMPLENTES
# ─────────────────────────────────────────
def pagina_top_inadimplentes(story, st, dados, analise):
    story.append(PageBreak())
    story.append(Paragraph("Top 20 Inadimplentes - detalhado", st['titulo']))
    story.append(Paragraph(f"{len(dados['resumo_v'])} clientes vencidos no total - "
                           f"detalhamento dos 20 maiores", st['subtitulo']))

    # Bola de neve - destaque
    bn = analise['bola_neve']
    if bn:
        story.append(Paragraph("ALERTA - Clientes em bola de neve", st['h2']))
        story.append(Paragraph(
            "Clientes ja inadimplentes que tem nova parcela vencendo nos proximos "
            "7 dias. Confirme antes do vencimento.", st['normal']))
        story.append(Spacer(1, 0.2*cm))
        bn_data = [["Cliente", "Vencido", "+ A vencer 7d", "Nova parcela"]]
        for b in bn[:10]:
            bn_data.append([
                b['cliente'][:42],
                fm(b['vencido']),
                fm(b['a_vencer_proxima']),
                b['data_proxima'].strftime('%d/%m/%Y') if b['data_proxima'] else '-',
            ])
        bn_table = Table(bn_data,
                         colWidths=[7*cm, 3*cm, 3.5*cm, 3.5*cm])
        bn_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), LARANJA),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 8.5),
            ('GRID',       (0,0), (-1,-1), 0.3, CINZA_M),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN',      (1,0), (-1,-1), 'RIGHT'),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING',(0,0), (-1,-1), 4),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_C]),
        ]))
        story.append(bn_table)
        story.append(Spacer(1, 0.4*cm))

    # Top 20 inadimplentes
    story.append(Paragraph("Top 20 com telefone e sistema", st['h2']))
    top20 = dados['resumo_v'][:20]
    data = [["#", "Cliente", "Valor", "Parc.", "Atraso", "Telefone", "Origem"]]
    for i, r in enumerate(top20, 1):
        data.append([
            str(i),
            r['cliente'][:32],
            fm(r['valor_total']),
            str(r.get('parcelas', 0)),
            f"{r['max_atraso']} d",
            r.get('telefone', '') or '-',
            r.get('sistemas', ''),
        ])
    tbl = Table(data, colWidths=[0.7*cm, 5.5*cm, 2.5*cm, 1*cm, 1.3*cm,
                                   3*cm, 2.8*cm])
    style = [
        ('BACKGROUND', (0,0), (-1,0), AZUL_ESC),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 8),
        ('GRID',       (0,0), (-1,-1), 0.3, CINZA_M),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (2,0), (4,-1), 'RIGHT'),
        ('ALIGN',      (0,0), (0,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING',(0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_C]),
    ]
    # Coluna atraso colorida
    for i, r in enumerate(top20, 1):
        c = cor_atraso(r['max_atraso'])
        style.append(('TEXTCOLOR', (4,i), (4,i), c))
        style.append(('FONTNAME', (4,i), (4,i), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(style))
    story.append(tbl)


# ─────────────────────────────────────────
# PAGINA 4 - LISTA COMPLETA
# ─────────────────────────────────────────
def pagina_lista_completa(story, st, dados):
    story.append(PageBreak())
    story.append(Paragraph("Lista completa - todos os inadimplentes",
                           st['titulo']))
    story.append(Paragraph(f"{len(dados['resumo_v'])} clientes - "
                           f"ordenado por urgencia e valor",
                           st['subtitulo']))

    data = [["#", "Cliente", "Valor", "Parc.", "Atraso", "Origem"]]
    for i, r in enumerate(dados['resumo_v'], 1):
        data.append([
            str(i),
            r['cliente'][:42],
            fm(r['valor_total']),
            str(r.get('parcelas', 0)),
            f"{r['max_atraso']}",
            r.get('sistemas', '')[:18],
        ])
    tbl = Table(data,
                colWidths=[0.8*cm, 7*cm, 2.7*cm, 1*cm, 1.3*cm, 4*cm],
                repeatRows=1)
    style = [
        ('BACKGROUND', (0,0), (-1,0), AZUL_ESC),
        ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
        ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0,0), (-1,-1), 7.5),
        ('GRID',       (0,0), (-1,-1), 0.2, CINZA_M),
        ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',      (2,0), (4,-1), 'RIGHT'),
        ('ALIGN',      (0,0), (0,-1), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING',(0,0), (-1,-1), 3),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, CINZA_C]),
    ]
    for i, r in enumerate(dados['resumo_v'], 1):
        c = cor_atraso(r['max_atraso'])
        style.append(('TEXTCOLOR', (4,i), (4,i), c))
        style.append(('FONTNAME', (4,i), (4,i), 'Helvetica-Bold'))
    tbl.setStyle(TableStyle(style))
    story.append(tbl)


# ─────────────────────────────────────────
# RODAPE
# ─────────────────────────────────────────
def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(CINZA_M)
    rodape = (f"JK Artes Graficas - Cobranca - "
              f"Pagina {doc.page} - "
              f"Gerado em {date.today().strftime('%d/%m/%Y')}")
    canvas.drawString(2*cm, 1*cm, rodape)
    canvas.drawRightString(A4[0] - 2*cm, 1*cm, "Confidencial")
    canvas.restoreState()


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def gerar(dados, analise, caminho=None):
    """
    Gera o PDF executivo. Retorna o caminho do arquivo.
    dados:   dict do atualizar_planilha.main()
    analise: dict do analises.montar_analise_completa()
    """
    if caminho is None:
        nome = f"cobranca_{date.today().strftime('%Y-%m-%d')}.pdf"
        caminho = os.path.join(PDFS_DIR, nome)

    doc = SimpleDocTemplate(
        caminho, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        title="Cobranca JK Artes Graficas",
        author="Agente de Cobranca JK",
    )

    st = make_styles()
    story = []

    pagina_resumo(story, st, dados, analise)
    pagina_recebimento(story, st, dados, analise)
    pagina_top_inadimplentes(story, st, dados, analise)
    pagina_lista_completa(story, st, dados)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    print(f"PDF gerado: {caminho}")
    return caminho


if __name__ == "__main__":
    # Teste isolado
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    from processar_cobranca import carregar_dados
    from analises import montar_analise_completa

    resumo_v, resumo_av, zen, mub = carregar_dados()
    total_v  = sum(r['valor_total'] for r in resumo_v)
    total_av = sum(r['valor_total'] for r in resumo_av)
    dados = {
        'resumo_v': resumo_v, 'resumo_av': resumo_av,
        'zen': zen, 'mub': mub,
        'total_v': total_v, 'total_av': total_av,
        'snapshot_anterior': None, 'clientes_ontem': None,
    }
    analise = montar_analise_completa(resumo_v, resumo_av, total_v, total_av,
                                       None, None)
    gerar(dados, analise)
