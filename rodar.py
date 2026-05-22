"""
Orquestrador principal - Agente de Cobranca JK
Executa tudo em sequencia:
  1. Processa dados + atualiza Google Sheets
  2. Gera PDF executivo em pdfs/ (no GitHub Actions vira artifact)
  3. Envia resumo por EMAIL (SMTP Gmail) com PDF anexo

Email substituiu o WhatsApp/Digisac em 22/05/2026 apos ban dos numeros JK.
Tambem alinha com os outros agentes financeiros (pagar, fluxo-caixa) ja em email.
"""

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


def main():
    log("=" * 55)
    log("  AGENTE DE COBRANCA JK ARTES GRAFICAS")
    log("=" * 55)

    erros = []
    planilha_ok = False
    resultado = None
    caminho_pdf = None
    arquivo_faltando = None

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
    except FileNotFoundError as e:
        log(f"ERRO na planilha (arquivo faltando): {e}")
        erros.append(f"planilha: {e}")
        msg = str(e).lower()
        if "mubys" in msg or "mubisys" in msg:
            arquivo_faltando = "mubisys.xls"
        elif "zenetti" in msg:
            arquivo_faltando = "zenetti.csv"
        else:
            arquivo_faltando = str(e)
    except Exception as e:
        log(f"ERRO na planilha: {e}")
        traceback.print_exc()
        erros.append(f"planilha: {e}")

    # 2. Gerar PDF (vai para pdfs/ - no Actions vira artifact)
    if planilha_ok:
        try:
            log("\nPasso 2/3 - Gerando PDF executivo...")
            from analises import montar_analise_completa
            from gerar_pdf import gerar as gerar_pdf

            analise = montar_analise_completa(
                resultado['resumo_v'], resultado['resumo_av'],
                resultado['total_v'], resultado['total_av'],
                resultado['snapshot_anterior'], resultado['clientes_ontem'],
            )
            caminho_pdf = gerar_pdf(resultado, analise)
            log(f"PDF gerado em: {caminho_pdf}")
        except Exception as e:
            log(f"ERRO no PDF: {e}")
            traceback.print_exc()
            erros.append(f"pdf: {e}")
    else:
        log("\nPasso 2/3 - PDF PULADO (planilha falhou)")

    # 3. Enviar EMAIL
    if not planilha_ok:
        if arquivo_faltando:
            try:
                log(f"\nPasso 3/3 - Enviando alerta EMAIL ({arquivo_faltando} faltando)...")
                from enviar_email import enviar_alerta_arquivo_faltando
                enviar_alerta_arquivo_faltando(arquivo_faltando)
            except Exception as e:
                log(f"ERRO no alerta email: {e}")
                traceback.print_exc()
                erros.append(f"alerta_email: {e}")
        else:
            log("\nPasso 3/3 - EMAIL PULADO (planilha falhou, evitando envio vazio)")
    else:
        try:
            log("\nPasso 3/3 - Enviando EMAIL...")
            from enviar_email import enviar
            enviar(
                resultado['resumo_v'], resultado['resumo_av'],
                resultado['total_v'], resultado['total_av'],
                pdf_path=caminho_pdf,
                dry_run=("--dry-run" in sys.argv),
            )
        except Exception as e:
            log(f"ERRO no email: {e}")
            traceback.print_exc()
            erros.append(f"email: {e}")

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
    main()
