"""
Envio do Relatorio de Cobranca via WhatsApp (Digisac)
JK Artes Graficas
"""

import asyncio
import httpx
import json
import re
import sys
from datetime import date

DIGISAC_TOKEN      = "1c429d508f47b84de37d3aa735f5cfd676a21ceb"
DIGISAC_BASE_URL   = "https://pontualcarimbos.digisac.co/api/v1"
DIGISAC_SERVICE_ID = "37d03d8c-f305-4a8b-ad29-c946f55f7258"
DATA_HOJE          = date.today()

DESTINATARIOS = [
    {"nome": "Luiz Otavio", "fone": "5543991134399"},
]

HEADERS = {
    "Authorization": f"Bearer {DIGISAC_TOKEN}",
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
}

def _post_json(payload):
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")

async def enviar_mensagem(fone, texto):
    url = f"{DIGISAC_BASE_URL}/messages"
    payload = {"number": fone, "serviceId": DIGISAC_SERVICE_ID, "text": texto}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, content=_post_json(payload), headers=HEADERS)
        if resp.is_success:
            print(f"  Enviado para {fone}")
            return True
        print(f"  Erro {resp.status_code}: {resp.text[:200]}")
        return False

async def enviar_alerta_arquivo_faltando(arquivo_faltando):
    """Avisa o Luiz que o relatorio de hoje nao saiu porque falta arquivo na pasta Entrada."""
    hoje = DATA_HOJE.strftime('%d/%m/%Y')
    texto = (
        f"*COBRANCA JK - RELATORIO NAO ENVIADO*\n"
        f"Data: {hoje}\n\n"
        f"Nao consegui gerar o relatorio de hoje porque *nao encontrei o arquivo* "
        f"`{arquivo_faltando}` na pasta Entrada do Drive.\n\n"
        f"_Acoes:_\n"
        f"1) Subir o arquivo `{arquivo_faltando}` na pasta Entrada\n"
        f"2) Avisar Fabricio pra disparar o relatorio manual\n\n"
        f"_Alerta automatico_"
    )
    for dest in DESTINATARIOS:
        print(f"Enviando alerta para {dest['nome']} ({dest['fone']})...")
        await enviar_mensagem(dest["fone"], texto)

def montar_mensagem(resumo_v, resumo_av, total_v, total_av, link_pdf=None):
    hoje = DATA_HOJE.strftime('%d/%m/%Y')
    total_g = total_v + total_av

    def fm(v):
        return f"R$ {v:,.2f}".replace(',','X').replace('.',',').replace('X','.')

    linhas = [
        f"*COBRANCA JK ARTES GRAFICAS*",
        f"Data: {hoje}",
        "",
        f"*Resumo Geral*",
        f"Total vencido:  *{fm(total_v)}* ({len(resumo_v)} clientes)",
        f"Total a vencer: *{fm(total_av)}* ({len(resumo_av)} clientes)",
        f"Total geral:    *{fm(total_g)}*",
        "",
        f"*Top 20 Inadimplentes*",
    ]

    for i, r in enumerate(resumo_v[:20], 1):
        urgencia = "🔴" if r['max_atraso'] > 90 else "🟠" if r['max_atraso'] > 60 else "🟡" if r['max_atraso'] > 30 else "🟢"
        linhas.append(
            f"{urgencia} {i:02d}. {r['cliente']}\n"
            f"    *{fm(r['valor_total'])}* | {r['parcelas']} parcela(s) | {r['max_atraso']} dias"
        )

    if len(resumo_v) > 20:
        linhas.append(f"\n... e mais {len(resumo_v) - 20} clientes.")

    if resumo_av:
        linhas += [
            "",
            f"*Proximos Vencimentos (Top 3)*",
        ]
        for r in resumo_av[:3]:
            from processar_cobranca import formatar_data
            linhas.append(
                f"📅 {r['cliente']}\n"
                f"    *{fm(r['valor_total'])}* | vence {formatar_data(r['mais_proxima'])}"
            )

    if link_pdf:
        linhas += ["", f"*Relatorio completo (PDF):*", link_pdf]

    linhas.append("\n_Relatorio gerado automaticamente_")
    return "\n".join(linhas)

async def main(resumo_v=None, resumo_av=None, total_v=None, total_av=None, link_pdf=None):
    print("=" * 55)
    print("  ENVIO WHATSAPP - COBRANCA JK")
    print("=" * 55)

    # Se nao recebeu dados, carrega
    if resumo_v is None:
        from processar_cobranca import carregar_dados
        resumo_v, resumo_av, _, _ = carregar_dados()
        total_v  = sum(r['valor_total'] for r in resumo_v)
        total_av = sum(r['valor_total'] for r in resumo_av)

    mensagem = montar_mensagem(resumo_v, resumo_av, total_v, total_av, link_pdf=link_pdf)
    print("\n--- PREVIEW ---")
    print(mensagem)
    print("---------------\n")

    modo_teste = "--teste" in sys.argv
    destinos = [{"nome": "Teste", "fone": "5543991134399"}] if modo_teste else DESTINATARIOS

    for dest in destinos:
        print(f"Enviando para {dest['nome']} ({dest['fone']})...")
        await enviar_mensagem(dest["fone"], mensagem)

    print("\nConcluido!")

if __name__ == "__main__":
    asyncio.run(main())
