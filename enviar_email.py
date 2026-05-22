"""Envio do Relatorio diario de Cobranca via email (SMTP Gmail).

Substituiu o envio via Digisac/WhatsApp em 22/05/2026 apos ban dos numeros
WhatsApp da JK. Tambem alinha com o padrao dos outros agentes financeiros
(pagar, fluxo-caixa) que ja estavam em email por privacidade.

Configuracao via env vars:
- GMAIL_USER              - conta gmail remetente (ex.: janfabricio@gmail.com)
- GMAIL_APP_PASSWORD      - 16 chars da app password (com ou sem espacos)
- EMAIL_DESTINATARIOS     - lista separada por virgula
"""
from __future__ import annotations

import os
import smtplib
import ssl
import sys
from datetime import date
from email.message import EmailMessage
from pathlib import Path

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

DATA_HOJE = date.today()


def _parse_destinatarios(env_value: str | None) -> list[str]:
    raw = env_value or ""
    return [e.strip() for e in raw.split(",") if e.strip()]


def _fmt(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


CSS = """
<style>
  body { font-family: -apple-system, 'Segoe UI', Arial, sans-serif; color: #222; max-width: 760px; margin: 0 auto; padding: 16px; }
  h1 { color: #1D356E; font-size: 20px; margin-bottom: 4px; }
  h2 { color: #284EA0; font-size: 14px; margin-top: 22px; margin-bottom: 6px; border-bottom: 1px solid #E0E5EC; padding-bottom: 4px; }
  .totais { display: table; width: 100%; background: #F2F4F6; padding: 12px; border-radius: 6px; margin: 10px 0; }
  .totais td { padding: 4px 10px; font-size: 13px; }
  table.lista { border-collapse: collapse; width: 100%; font-size: 12px; }
  table.lista th { background: #1D356E; color: white; text-align: left; padding: 5px 6px; }
  table.lista td { padding: 4px 6px; border-bottom: 1px solid #EEE; vertical-align: top; }
  table.lista tr:nth-child(even) td { background: #FAFBFC; }
  .vermelho { color: #B22222; font-weight: bold; }
  .laranja  { color: #F47D1A; font-weight: bold; }
  .amarelo  { color: #C99500; font-weight: bold; }
  .verde    { color: #228B22; }
  .footer { color: #888; font-size: 11px; margin-top: 30px; padding-top: 10px; border-top: 1px solid #E0E5EC; }
</style>
"""


def _formatar_data_br(d) -> str:
    if not d:
        return "-"
    if isinstance(d, str):
        return d
    return d.strftime("%d/%m") if hasattr(d, "strftime") else str(d)


def montar_corpo_html(resumo_v, resumo_av, total_v, total_av, hoje):
    total_g = total_v + total_av

    H = [f"<!doctype html><html><head><meta charset='utf-8'>{CSS}</head><body>"]
    H.append("<h1>Cobranca - JK Artes Graficas</h1>")
    H.append(f"<div style='color:#888;font-size:12px;'>Resumo de {hoje.strftime('%d/%m/%Y')}</div>")

    H.append("<div class='totais'><table><tr>")
    H.append(f"<td><b class='vermelho'>Vencido:</b> {_fmt(total_v)} ({len(resumo_v)} clientes)</td>")
    H.append(f"<td><b class='verde'>A vencer:</b> {_fmt(total_av)} ({len(resumo_av)} clientes)</td>")
    H.append(f"<td><b>Total geral:</b> {_fmt(total_g)}</td>")
    H.append("</tr></table></div>")

    if resumo_v:
        H.append("<h2>Top 20 inadimplentes (por valor)</h2>")
        H.append("<table class='lista'><tr><th>#</th><th>Cliente</th><th>Parcelas</th><th>Pior atraso</th><th style='text-align:right'>Valor</th></tr>")
        for i, r in enumerate(resumo_v[:20], 1):
            atraso = r.get("max_atraso", 0)
            cor = "vermelho" if atraso > 90 else "laranja" if atraso > 60 else "amarelo" if atraso > 30 else "verde"
            H.append(
                f"<tr><td>{i:02d}</td>"
                f"<td>{r['cliente'][:40]}</td>"
                f"<td>{r.get('parcelas', '-')}</td>"
                f"<td class='{cor}'>{atraso}d</td>"
                f"<td style='text-align:right'><b>{_fmt(r['valor_total'])}</b></td></tr>"
            )
        H.append("</table>")
        if len(resumo_v) > 20:
            H.append(f"<div style='color:#888;font-size:11px;margin-top:4px'>... mais {len(resumo_v) - 20} cliente(s) inadimplente(s) no PDF anexo.</div>")

    if resumo_av:
        H.append("<h2>Proximos vencimentos - Top 10</h2>")
        H.append("<table class='lista'><tr><th>#</th><th>Cliente</th><th>Vence</th><th style='text-align:right'>Valor</th></tr>")
        for i, r in enumerate(resumo_av[:10], 1):
            H.append(
                f"<tr><td>{i:02d}</td>"
                f"<td>{r['cliente'][:40]}</td>"
                f"<td>{_formatar_data_br(r.get('mais_proxima'))}</td>"
                f"<td style='text-align:right'><b>{_fmt(r['valor_total'])}</b></td></tr>"
            )
        H.append("</table>")

    H.append(
        "<div class='footer'>"
        "PDF executivo em anexo (4 paginas com analise completa).<br>"
        "Relatorio gerado automaticamente - seg-sab 07h BRT<br>"
        "<b>CONFIDENCIAL - uso interno restrito.</b>"
        "</div>"
    )
    H.append("</body></html>")
    return "".join(H)


def montar_corpo_texto(resumo_v, resumo_av, total_v, total_av, hoje):
    L = [
        f"COBRANCA - JK ({hoje.strftime('%d/%m/%Y')})",
        f"Vencido: {_fmt(total_v)} ({len(resumo_v)} clientes)",
        f"A vencer: {_fmt(total_av)} ({len(resumo_av)} clientes)",
        f"Total: {_fmt(total_v + total_av)}",
        "",
        "TOP 10 INADIMPLENTES:",
    ]
    for i, r in enumerate(resumo_v[:10], 1):
        L.append(f"{i:02d}. {r['cliente'][:35]} | {_fmt(r['valor_total'])} | {r.get('max_atraso', 0)}d")
    L.append("")
    L.append("Veja o PDF anexo pra analise completa.")
    return "\n".join(L)


def enviar(resumo_v, resumo_av, total_v, total_av, *, pdf_path=None, hoje=None, dry_run=False):
    if hoje is None:
        hoje = DATA_HOJE

    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    destinatarios = _parse_destinatarios(os.environ.get("EMAIL_DESTINATARIOS"))

    if not gmail_user or not app_password:
        raise RuntimeError("Configure GMAIL_USER e GMAIL_APP_PASSWORD nas env vars / secrets.")
    if not destinatarios:
        raise RuntimeError("Configure EMAIL_DESTINATARIOS (emails separados por virgula).")

    assunto = (
        f"[CONFIDENCIAL - Financeiro JK] Cobranca {hoje.strftime('%d/%m/%Y')} - "
        f"Vencido {_fmt(total_v)} ({len(resumo_v)} clientes)"
    )

    msg = EmailMessage()
    msg["From"] = f"Agente Cobranca JK <{gmail_user}>"
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = assunto
    msg["X-Priority"] = "1"

    corpo_txt = montar_corpo_texto(resumo_v, resumo_av, total_v, total_av, hoje)
    corpo_html = montar_corpo_html(resumo_v, resumo_av, total_v, total_av, hoje)
    msg.set_content(corpo_txt)
    msg.add_alternative(corpo_html, subtype="html")

    if pdf_path:
        p = Path(pdf_path)
        if p.exists():
            data = p.read_bytes()
            msg.add_attachment(
                data, maintype="application", subtype="pdf", filename=p.name,
            )
            print(f"  PDF anexo: {p.name} ({len(data) / 1024:.1f} KB)")

    print("=" * 60)
    print("  ENVIO EMAIL - COBRANCA JK")
    print("=" * 60)
    print(f"De:    {gmail_user}")
    print(f"Para:  {destinatarios}")
    print(f"Assunto: {assunto}")

    if dry_run or "--dry-run" in sys.argv:
        print("(dry-run; sem envio SMTP)")
        return True

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(gmail_user, app_password)
        server.send_message(msg)
    print(f"  Email enviado pra {len(destinatarios)} destinatario(s).")
    return True


def enviar_alerta_arquivo_faltando(arquivo_faltando, *, hoje=None):
    """Avisa que o relatorio nao saiu porque falta arquivo na pasta Entrada."""
    if hoje is None:
        hoje = DATA_HOJE

    gmail_user = os.environ.get("GMAIL_USER", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    destinatarios = _parse_destinatarios(os.environ.get("EMAIL_DESTINATARIOS"))

    if not gmail_user or not app_password or not destinatarios:
        print("  Alerta nao enviado: env vars de email faltando")
        return False

    assunto = f"[ALERTA - Cobranca JK] Relatorio {hoje.strftime('%d/%m/%Y')} NAO ENVIADO - {arquivo_faltando} faltando"
    corpo = (
        f"<h2 style='color:#B22222'>Cobranca JK - Relatorio nao enviado</h2>"
        f"<p>Data: <b>{hoje.strftime('%d/%m/%Y')}</b></p>"
        f"<p>Nao foi possivel gerar o relatorio de hoje porque <b>nao encontrei o arquivo</b> "
        f"<code>{arquivo_faltando}</code> na pasta Entrada do Drive.</p>"
        f"<p><b>Acoes:</b></p>"
        f"<ol>"
        f"<li>Subir o arquivo <code>{arquivo_faltando}</code> na pasta Entrada</li>"
        f"<li>Rodar manualmente o workflow no GitHub Actions ou aguardar o cron do proximo dia util</li>"
        f"</ol>"
        f"<hr><p style='color:#888;font-size:11px'>Alerta automatico - Agente Cobranca JK</p>"
    )

    msg = EmailMessage()
    msg["From"] = f"Agente Cobranca JK <{gmail_user}>"
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = assunto
    msg["X-Priority"] = "1"
    msg.set_content(f"Relatorio cobranca {hoje.strftime('%d/%m/%Y')} nao enviado. Arquivo faltando: {arquivo_faltando}")
    msg.add_alternative(corpo, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(gmail_user, app_password)
        server.send_message(msg)
    print(f"  Alerta enviado pra {len(destinatarios)} destinatario(s).")
    return True


if __name__ == "__main__":
    from processar_cobranca import carregar_dados
    resumo_v, resumo_av, _, _ = carregar_dados()
    total_v = sum(r['valor_total'] for r in resumo_v)
    total_av = sum(r['valor_total'] for r in resumo_av)
    enviar(resumo_v, resumo_av, total_v, total_av, dry_run=("--dry-run" in sys.argv))
