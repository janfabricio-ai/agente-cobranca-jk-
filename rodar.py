"""
Orquestrador principal - Agente de Cobranca JK
Executa tudo em sequencia:
  1. Processa dados + atualiza Google Sheets
  2. Gera PDF executivo + faz upload para a pasta Cobranca no Drive
  3. Envia resumo no WhatsApp (com link do PDF)
"""

import asyncio
import sys
import traceback
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

async def main():
    log("=" * 55)
    log("  AGENTE DE COBRANCA JK ARTES GRAFICAS")
    log("=" * 55)

    erros = []
    planilha_ok = False
    resultado = None
    link_pdf = None

    # 1. Processar + Atualizar planilha
    try:
        log("\nPasso 1/3 - Processando dados e atualizando planilha...")
        from atualizar_planilha import main as atualizar
        resultado = atualizar()
        if resultado:
            planilha_ok = True
            log("Planilha atualizada com sucesso")
        else:
            erros.append("atualizar_planilha nao retornou dados")
    except Exception as e:
        log(f"ERRO na planilha: {e}")
        traceback.print_exc()
        erros.append(f"planilha: {e}")

    # 2. Gerar PDF + upload Drive
    if planilha_ok:
        try:
            log("\nPasso 2/3 - Gerando PDF e enviando para o Drive...")
            from analises import montar_analise_completa
            from gerar_pdf import gerar as gerar_pdf
            from upload_drive import carregar_ids, upload_arquivo

            analise = montar_analise_completa(
                resultado['resumo_v'], resultado['resumo_av'],
                resultado['total_v'], resultado['total_av'],
                resultado['snapshot_anterior'], resultado['clientes_ontem'],
            )
            caminho_pdf = gerar_pdf(resultado, analise)
            ids = carregar_ids()
            link_pdf = upload_arquivo(caminho_pdf, ids["pasta_cobranca"])
            log(f"PDF no Drive: {link_pdf}")
        except Exception as e:
            log(f"ERRO no PDF/upload: {e}")
            traceback.print_exc()
            erros.append(f"pdf: {e}")
    else:
        log("\nPasso 2/3 - PDF PULADO (planilha falhou)")

    # 3. Enviar WhatsApp (somente se planilha OK)
    if not planilha_ok:
        log("\nPasso 3/3 - WhatsApp PULADO (planilha falhou, evitando envio vazio)")
    else:
        try:
            log("\nPasso 3/3 - Enviando WhatsApp...")
            from enviar_whatsapp import main as enviar
            await enviar(
                resultado['resumo_v'], resultado['resumo_av'],
                resultado['total_v'], resultado['total_av'],
                link_pdf=link_pdf,
            )
        except Exception as e:
            log(f"ERRO no WhatsApp: {e}")
            traceback.print_exc()
            erros.append(f"whatsapp: {e}")

    # Resumo final
    log("\n" + "=" * 55)
    if erros:
        log(f"  CONCLUIDO COM {len(erros)} ERRO(S):")
        for e in erros:
            log(f"    - {e}")
        sys.exit(1)
    else:
        log("  CONCLUIDO COM SUCESSO")
    log("=" * 55)

if __name__ == "__main__":
    asyncio.run(main())
