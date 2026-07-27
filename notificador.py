#!/usr/bin/env python3
"""Serviço de lembretes por e-mail da agenda simples.

Envia um e-mail 1 hora antes de cada evento, com os detalhes do
agendamento. Reaproveita a lógica do agenda.py e usa apenas a stdlib
(smtplib + email).

Configuração via variáveis de ambiente (ou um arquivo .env ao lado do script):
  SMTP_HOST        ex.: smtp.gmail.com
  SMTP_PORT        587 (STARTTLS) ou 465 (SSL). Padrão 587.
  SMTP_USER        usuário/login SMTP
  SMTP_PASSWORD    senha  (no Gmail use uma "Senha de app", não a senha normal)
  SMTP_FROM        remetente (padrão = SMTP_USER)
  AGENDA_EMAIL_TO  destinatário padrão dos lembretes

Uso:
  python notificador.py                 # loop: checa a cada 60s e envia
  python notificador.py --once          # checa uma vez e sai (Agendador/cron)
  python notificador.py --interval 30   # intervalo do loop em segundos
  python notificador.py --dry-run       # NÃO envia; imprime o e-mail que enviaria
  python notificador.py --test dest@x.com   # envia um e-mail de teste e sai
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import agenda  # reaproveita carregar()/expandir()/ALERTA_MIN (tambem ajusta stdout p/ utf-8)

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")  # mensagens de erro legiveis no Windows

ALERTA_MIN = agenda.ALERTA_MIN
ENVIADOS = Path(__file__).with_name("enviados.json")


# --------------------------------------------------------------------- config
def carregar_env(caminho):
    """Carrega KEY=VALUE de um .env simples, sem sobrescrever o ambiente."""
    p = Path(caminho)
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def carregar_config():
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    senha = os.environ.get("SMTP_PASSWORD")
    to = os.environ.get("AGENDA_EMAIL_TO")
    faltando = [n for n, v in [("SMTP_HOST", host), ("SMTP_USER", user),
                               ("SMTP_PASSWORD", senha),
                               ("AGENDA_EMAIL_TO", to)] if not v]
    if faltando:
        sys.exit("Configuração faltando: " + ", ".join(faltando) +
                 "\nDefina as variáveis de ambiente ou preencha um arquivo .env "
                 "(veja .env.example).")
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": user,
        "password": senha,
        "from": os.environ.get("SMTP_FROM") or user,
        "to": to,
    }


# ------------------------------------------------------------------ dedup db
def carregar_enviados():
    if ENVIADOS.exists():
        return set(json.loads(ENVIADOS.read_text(encoding="utf-8")))
    return set()


def salvar_enviados(chaves, agora):
    """Persiste as chaves, descartando ocorrencias com mais de 1 dia."""
    limite = agora - timedelta(days=1)
    manter = []
    for k in chaves:
        try:
            occ = datetime.fromisoformat(k.split("|", 1)[1])
        except (ValueError, IndexError):
            continue
        if occ >= limite:
            manter.append(k)
    ENVIADOS.write_text(json.dumps(sorted(manter), ensure_ascii=False, indent=2),
                        encoding="utf-8")


# ------------------------------------------------------------------ e-mail
def montar_email(e, occ, cfg):
    ini = occ
    fim = ini + timedelta(minutes=e["dur"]) if e.get("dur") else None
    quando = f"{ini:%d/%m/%Y %H:%M}" + (f"–{fim:%H:%M}" if fim else "")

    linhas = [f"Lembrete: seu evento começa em {ALERTA_MIN} minutos.", "",
              f"• Evento: {e['titulo']}",
              f"• Quando: {quando}"]
    if e.get("dur"):
        linhas.append(f"• Duração: {e['dur']} min")
    if e.get("desc"):
        linhas.append(f"• Descrição: {e['desc']}")
    if e.get("repeat"):
        linhas.append(f"• Recorrência: {e['repeat']}")
    linhas += ["", "— Agenda Simples"]

    msg = EmailMessage()
    msg["Subject"] = f"⏰ Lembrete: {e['titulo']} às {ini:%H:%M}"
    msg["From"] = cfg["from"]
    msg["To"] = e.get("to") or cfg["to"]
    msg.set_content("\n".join(linhas))
    return msg


def enviar(msg, cfg):
    import smtplib

    if cfg["port"] == 465:
        with smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30) as s:
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as s:
            s.starttls()
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)


# ------------------------------------------------------------------ processo
def processar(cfg, dry_run=False):
    """Uma passada: envia lembrete dos eventos que entram na janela de 1 hora."""
    agora = datetime.now()
    janela = agenda.expandir(agenda.carregar(), agora,
                             agora + timedelta(minutes=ALERTA_MIN))
    enviados = carregar_enviados()
    novos = 0
    for occ, e in janela:
        chave = f"{e['id']}|{occ.isoformat()}"
        if chave in enviados:
            continue
        msg = montar_email(e, occ, cfg)
        if dry_run:
            print("---- (dry-run) enviaria ------------------------------")
            print(f"To: {msg['To']}")
            print(f"Subject: {msg['Subject']}\n")
            print(msg.get_content())
        else:
            enviar(msg, cfg)
            print(f"[{agora:%H:%M}] E-mail enviado: '{e['titulo']}' → "
                  f"{msg['To']} (inicia {occ:%H:%M})")
        enviados.add(chave)
        novos += 1

    if not dry_run:
        salvar_enviados(enviados, agora)
    return novos


# ------------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser(description="Serviço de lembretes por e-mail.")
    p.add_argument("--once", action="store_true",
                   help="checa uma vez e sai (para Agendador de Tarefas/cron)")
    p.add_argument("--interval", type=int, default=60,
                   help="segundos entre checagens no modo loop")
    p.add_argument("--dry-run", action="store_true",
                   help="não envia; imprime o e-mail que seria enviado")
    p.add_argument("--test", metavar="EMAIL", nargs="?", const="",
                   help="envia um e-mail de teste (usa AGENDA_EMAIL_TO se vazio)")
    p.add_argument("--env", default=str(Path(__file__).with_name(".env")),
                   help="caminho do arquivo .env")
    args = p.parse_args()

    carregar_env(args.env)
    cfg = carregar_config()

    if args.test is not None:
        msg = EmailMessage()
        msg["Subject"] = "✅ Teste — Agenda Simples"
        msg["From"] = cfg["from"]
        msg["To"] = args.test or cfg["to"]
        msg.set_content("E-mail de teste do serviço de lembretes da Agenda "
                        "Simples.\nSe você recebeu, o SMTP está configurado "
                        "corretamente.")
        enviar(msg, cfg)
        print(f"E-mail de teste enviado para {msg['To']}.")
        return

    if args.once:
        n = processar(cfg, args.dry_run)
        print(f"{n} lembrete(s) processado(s).")
        return

    print(f"Serviço de lembretes ativo (1 hora antes, checa a cada "
          f"{args.interval}s). Ctrl+C para sair.")
    try:
        while True:
            try:
                processar(cfg, args.dry_run)
            except Exception as ex:  # nao derruba o serviço por falha pontual
                print(f"[erro] {ex}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nServiço encerrado.")


if __name__ == "__main__":
    main()
