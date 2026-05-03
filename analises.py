"""
Analises e heuristicas para o relatorio de cobranca.
Tudo o que e calculo puro (sem IA) fica aqui.
"""

from datetime import date, timedelta
from collections import defaultdict


def calcular_aging(resumo_v):
    """
    Distribui o vencido em 4 faixas de atraso.
    Retorna dict com {faixa: {'qtd': N, 'valor': X, 'pct': %}}.
    """
    faixas = {
        '0-30':  {'qtd': 0, 'valor': 0.0},
        '31-60': {'qtd': 0, 'valor': 0.0},
        '61-90': {'qtd': 0, 'valor': 0.0},
        '90+':   {'qtd': 0, 'valor': 0.0},
    }
    for r in resumo_v:
        d = r['max_atraso']
        if d <= 30:    faixa = '0-30'
        elif d <= 60:  faixa = '31-60'
        elif d <= 90:  faixa = '61-90'
        else:          faixa = '90+'
        faixas[faixa]['qtd']   += 1
        faixas[faixa]['valor'] += r['valor_total']

    total = sum(f['valor'] for f in faixas.values()) or 1
    for f in faixas.values():
        f['pct'] = (f['valor'] / total) * 100
    return faixas


def calcular_concentracao(resumo_v, top_n=5):
    """
    Quanto os top N clientes representam do total.
    Retorna {'top': [...], 'valor_top': X, 'pct_top': %, 'total': Y}.
    """
    total = sum(r['valor_total'] for r in resumo_v) or 1
    top = resumo_v[:top_n]
    valor_top = sum(r['valor_total'] for r in top)
    return {
        'top': top,
        'valor_top': valor_top,
        'pct_top': (valor_top / total) * 100,
        'total': total,
    }


def calcular_comparativo(total_v, total_av, qtd_v, qtd_av, snapshot_anterior):
    """
    Variacao vs. dia anterior. Retorna dict ou None se nao ha snapshot.
    """
    if not snapshot_anterior:
        return None
    return {
        'data_anterior': snapshot_anterior['data'],
        'delta_v_abs':   total_v - snapshot_anterior['vencido_total'],
        'delta_v_pct':   ((total_v / snapshot_anterior['vencido_total'] - 1) * 100
                          if snapshot_anterior['vencido_total'] else 0),
        'delta_av_abs':  total_av - snapshot_anterior['a_vencer_total'],
        'delta_av_pct':  ((total_av / snapshot_anterior['a_vencer_total'] - 1) * 100
                          if snapshot_anterior['a_vencer_total'] else 0),
        'delta_qtd_v':   qtd_v - snapshot_anterior['vencido_qtd'],
        'delta_qtd_av':  qtd_av - snapshot_anterior['a_vencer_qtd'],
    }


def detectar_entrada_saida(resumo_v, clientes_ontem):
    """
    Quem entrou (novos inadimplentes) e quem saiu (quitou) vs. ontem.
    Retorna {'novos': [...], 'quitados': [...]}.
    """
    if not clientes_ontem:
        return {'novos': [], 'quitados': []}

    hoje_set = {r['cliente'] for r in resumo_v}
    ontem_set = set(clientes_ontem.keys())

    novos_nomes    = hoje_set - ontem_set
    quitados_nomes = ontem_set - hoje_set

    novos = [r for r in resumo_v if r['cliente'] in novos_nomes]
    quitados = [{'cliente': nome, 'valor_total': clientes_ontem[nome]}
                for nome in quitados_nomes]
    quitados.sort(key=lambda x: x['valor_total'], reverse=True)
    return {'novos': novos, 'quitados': quitados}


def detectar_bola_de_neve(resumo_v, resumo_av, dias=7):
    """
    Clientes JA vencidos que tem parcelas vencendo nos proximos N dias.
    Risco alto de inadimplencia em cadeia.
    Retorna lista de dicts.
    """
    hoje = date.today()
    limite = hoje + timedelta(days=dias)

    av_por_cliente = defaultdict(lambda: {'valor': 0, 'mais_proxima': None})
    for r in resumo_av:
        if r.get('mais_proxima') and r['mais_proxima'] <= limite:
            av_por_cliente[r['cliente']]['valor']        += r['valor_total']
            av_por_cliente[r['cliente']]['mais_proxima']  = r['mais_proxima']

    vencidos_set = {r['cliente'] for r in resumo_v}
    bola_neve = []
    for cliente in vencidos_set & set(av_por_cliente.keys()):
        venc = next(r for r in resumo_v if r['cliente'] == cliente)
        bola_neve.append({
            'cliente': cliente,
            'vencido':         venc['valor_total'],
            'a_vencer_proxima': av_por_cliente[cliente]['valor'],
            'data_proxima':    av_por_cliente[cliente]['mais_proxima'],
            'max_atraso':      venc['max_atraso'],
        })
    bola_neve.sort(key=lambda x: x['vencido'] + x['a_vencer_proxima'], reverse=True)
    return bola_neve


def projecao_recebimento(resumo_av):
    """
    Projecao em janelas de 7, 15, 30 e 60 dias.
    Retorna dict {'7d': {...}, '15d': {...}, ...}.
    """
    hoje = date.today()
    janelas = {'7d': 7, '15d': 15, '30d': 30, '60d': 60}
    resultado = {}
    for nome, dias in janelas.items():
        limite = hoje + timedelta(days=dias)
        regs = [r for r in resumo_av if r.get('mais_proxima') and r['mais_proxima'] <= limite]
        resultado[nome] = {
            'qtd_clientes': len(regs),
            'valor':        sum(r['valor_total'] for r in regs),
            'limite':       limite,
        }
    return resultado


def calendario_diario(resumo_av, dias=14):
    """
    Valor a receber por dia nos proximos N dias.
    Soma TODAS as parcelas a vencer (nao so a mais proxima por cliente).
    Retorna lista [(data, valor, qtd), ...].
    """
    hoje = date.today()
    por_dia = defaultdict(lambda: {'valor': 0.0, 'qtd': 0})

    for r in resumo_av:
        for parcela in r.get('detalhes', []):
            d = parcela.get('vencimento')
            v = parcela.get('valor')
            if d and v and hoje <= d <= hoje + timedelta(days=dias):
                por_dia[d]['valor'] += v
                por_dia[d]['qtd']   += 1

    resultado = []
    for i in range(dias + 1):
        d = hoje + timedelta(days=i)
        info = por_dia.get(d, {'valor': 0.0, 'qtd': 0})
        resultado.append({'data': d, 'valor': info['valor'], 'qtd': info['qtd']})
    return resultado


def gerar_alertas(resumo_v, resumo_av, comparativo, bola_neve, aging, concentracao):
    """
    Gera lista de alertas/estrategias com regras heuristicas.
    Retorna lista de dicts {'nivel': 'critico|alto|medio', 'titulo': '...', 'detalhe': '...'}.
    """
    alertas = []

    # 1. Concentracao alta
    if concentracao['pct_top'] >= 50:
        alertas.append({
            'nivel': 'critico',
            'titulo': f"Concentracao critica: top 5 = {concentracao['pct_top']:.0f}% do vencido",
            'detalhe': f"R$ {concentracao['valor_top']:,.2f} concentrados em 5 clientes. "
                       f"Foco total na cobranca destes.",
        })
    elif concentracao['pct_top'] >= 35:
        alertas.append({
            'nivel': 'alto',
            'titulo': f"Concentracao relevante: top 5 = {concentracao['pct_top']:.0f}% do vencido",
            'detalhe': f"R$ {concentracao['valor_top']:,.2f} em 5 clientes — "
                       f"priorize ligacoes diretas hoje.",
        })

    # 2. Acima de 90 dias (provavel incobravel sem acao)
    if aging['90+']['qtd'] > 0:
        alertas.append({
            'nivel': 'critico',
            'titulo': f"{aging['90+']['qtd']} cliente(s) acima de 90 dias - R$ {aging['90+']['valor']:,.2f}",
            'detalhe': "Janela legal para protesto/negativacao. Risco alto de virar incobravel "
                       "se nao houver acao formal nos proximos dias.",
        })

    # 3. Bola de neve (vencido + nova parcela vencendo essa semana)
    if bola_neve:
        total_neve = sum(b['vencido'] + b['a_vencer_proxima'] for b in bola_neve)
        alertas.append({
            'nivel': 'alto',
            'titulo': f"Bola de neve: {len(bola_neve)} cliente(s) vencidos com nova parcela em 7 dias",
            'detalhe': f"R$ {total_neve:,.2f} em risco. Confirmar pagamento ANTES do novo vencimento "
                       f"para nao acumular dividas.",
        })

    # 4. Comparativo - piorou
    if comparativo and comparativo['delta_v_abs'] > 0:
        alertas.append({
            'nivel': 'alto' if comparativo['delta_v_pct'] > 5 else 'medio',
            'titulo': f"Vencido aumentou +R$ {comparativo['delta_v_abs']:,.2f} "
                      f"({comparativo['delta_v_pct']:+.1f}%) vs. {comparativo['data_anterior']}",
            'detalhe': f"Variacao de qtd: {comparativo['delta_qtd_v']:+d} cliente(s).",
        })

    # 5. Comparativo - melhorou
    if comparativo and comparativo['delta_v_abs'] < -100:
        alertas.append({
            'nivel': 'positivo',
            'titulo': f"Vencido reduziu R$ {abs(comparativo['delta_v_abs']):,.2f} "
                      f"({comparativo['delta_v_pct']:+.1f}%) vs. {comparativo['data_anterior']}",
            'detalhe': "Continue a estrategia atual de cobranca.",
        })

    return alertas


def estrategias_top_clientes(resumo_v, top_n=5):
    """
    Sugere acao para cada um dos top N inadimplentes baseado em regras.
    """
    sugestoes = []
    for r in resumo_v[:top_n]:
        atraso = r['max_atraso']
        valor  = r['valor_total']

        if atraso > 90 and valor > 5000:
            acao = "Protocolar protesto + carta formal de cobranca"
            urgencia = "CRITICA"
        elif atraso > 90:
            acao = "Negativar (Serasa/SPC) + ultimato escrito"
            urgencia = "CRITICA"
        elif atraso > 60 and valor > 3000:
            acao = "Ligacao direta com decisor + proposta de parcelamento"
            urgencia = "ALTA"
        elif atraso > 60:
            acao = "Notificacao formal + cobranca telefonica"
            urgencia = "ALTA"
        elif atraso > 30:
            acao = "Cobranca ativa por telefone/email"
            urgencia = "MEDIA"
        else:
            acao = "Lembrete amigavel"
            urgencia = "BAIXA"

        sugestoes.append({
            'cliente': r['cliente'],
            'valor':   valor,
            'atraso':  atraso,
            'parcelas': r.get('parcelas', 0),
            'acao':    acao,
            'urgencia': urgencia,
        })
    return sugestoes


def montar_analise_completa(resumo_v, resumo_av, total_v, total_av,
                             snapshot_anterior, clientes_ontem):
    """
    Roda todas as analises e retorna um dict consolidado.
    """
    aging         = calcular_aging(resumo_v)
    concentracao  = calcular_concentracao(resumo_v, top_n=5)
    comparativo   = calcular_comparativo(total_v, total_av, len(resumo_v),
                                         len(resumo_av), snapshot_anterior)
    entrada_saida = detectar_entrada_saida(resumo_v, clientes_ontem)
    bola_neve     = detectar_bola_de_neve(resumo_v, resumo_av, dias=7)
    projecao      = projecao_recebimento(resumo_av)
    calendario    = calendario_diario(resumo_av, dias=14)
    alertas       = gerar_alertas(resumo_v, resumo_av, comparativo, bola_neve,
                                  aging, concentracao)
    estrategias   = estrategias_top_clientes(resumo_v, top_n=5)

    return {
        'aging': aging,
        'concentracao': concentracao,
        'comparativo': comparativo,
        'entrada_saida': entrada_saida,
        'bola_neve': bola_neve,
        'projecao': projecao,
        'calendario': calendario,
        'alertas': alertas,
        'estrategias': estrategias,
    }
