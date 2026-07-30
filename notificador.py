#!/usr/bin/env python3
"""Serviço de lembretes (e-mail + Telegram) da agenda simples.

Envia:
  • E-mail 60 minutos (1 hora) antes de cada evento (via SMTP)
  • Mensagem Telegram 60 minutos (1 hora) antes (via API do bot)

Reaproveita a lógica do agenda.py e usa apenas stdlib (smtplib, email, urllib).

Configuração via variáveis de ambiente (ou um arquivo .env ao lado do script):
  SMTP_HOST        ex.: smtp.gmail.com
  SMTP_PORT        587 (STARTTLS) ou 465 (SSL). Padrão 587.
  SMTP_USER        usuário/login SMTP
  SMTP_PASSWORD    senha (no Gmail use uma "Senha de app")
  SMTP_FROM        remetente (padrão = SMTP_USER)
  AGENDA_EMAIL_TO  destinatário padrão dos lembretes por e-mail

  TELEGRAM_BOT_TOKEN    token do seu bot (@BotFather no Telegram)
  TELEGRAM_CHAT_ID      chat_id destinatário

Uso:
  python notificador.py                 # loop: checa a cada 60s e envia
  python notificador.py --once          # checa uma vez e sai (Agendador/cron)
  python notificador.py --interval 30   # intervalo do loop em segundos
  python notificador.py --dry-run       # NÃO envia; imprime o que seria enviado
  python notificador.py --test email@x  # e-mail de teste
  python notificador.py --test-tg       # mensagem Telegram de teste
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import agenda  # reaproveita carregar()/expandir()/ALERTA_MIN

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ALERTA_EMAIL = 60       # minutos (1 hora)
ALERTA_TELEGRAM = ALERTA_EMAIL  # mesma frequência que o e‑mail
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
    """Carrega e valida a config. Email e Telegram sao opcionais (nao bloqueantes)."""
    config = {}

    # E-mail (opcional)
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    senha = os.environ.get("SMTP_PASSWORD")
    to = os.environ.get("AGENDA_EMAIL_TO")
    if all([host, user, senha, to]):
        config["email"] = {
            "host": host,
            "port": int(os.environ.get("SMTP_PORT", "587")),
            "user": user,
            "password": senha,
            "from": os.environ.get("SMTP_FROM") or user,
            "to": to,
        }

    # Telegram (opcional)
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat:
        config["telegram"] = {
            "token": tg_token,
            "chat_id": tg_chat,
        }

    if not config:
        sys.exit("Nenhum serviço de notificacao configurado.\n"
                 "Configure SMTP (email) e/ou Telegram via .env ou variáveis de ambiente.")
    return config


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
            occ = datetime.fromisoformat(k.split("|", 2)[2])
        except (ValueError, IndexError):
            continue
        if occ >= limite:
            manter.append(k)
    ENVIADOS.write_text(json.dumps(sorted(manter), ensure_ascii=False, indent=2),
                        encoding="utf-8")


# ------------------------------------------------------------------ mensagens
def montar_mensagem(e, occ):
    """Monta o conteúdo da notificação (usado por email e Telegram)."""
    ini = occ
    fim = ini + timedelta(minutes=e["dur"]) if e.get("dur") else None
    quando = f"{ini:%d/%m/%Y %H:%M}" + (f"–{fim:%H:%M}" if fim else "")

    linhas = [f"Lembrete: seu evento começa em breve.", "",
              f"• Evento: {e['titulo']}",
              f"• Quando: {quando}"]
    if e.get("dur"):
        linhas.append(f"• Duração: {e['dur']} min")
    if e.get("desc"):
        linhas.append(f"• Descrição: {e['desc']}")
    if e.get("repeat"):
        linhas.append(f"• Recorrência: {e['repeat']}")
    linhas += ["", "— Agenda Simples"]
    return "\n".join(linhas)


# ------------------------------------------------------------------ e-mail
def montar_email(e, occ, cfg):
    msg = EmailMessage()
    msg["Subject"] = f"⏰ Lembrete: {e['titulo']} às {occ:%H:%M}"
    msg["From"] = cfg["from"]
    msg["To"] = e.get("to") or cfg["to"]
    msg.set_content(montar_mensagem(e, occ))
    return msg


def enviar_email(msg, cfg):
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


# ------------------------------------------------------------------ telegram
def enviar_telegram(titulo, mensagem, cfg):
    """Envia via API do Telegram (returns True se sucesso)."""
    url = f"https://api.telegram.org/bot{cfg['token']}/sendMessage"
    dados = urlencode({"chat_id": cfg["chat_id"], "text": mensagem})
    try:
        req = Request(url, data=dados.encode("utf-8"))
        urlopen(req, timeout=30)
        return True
    except Exception as ex:
        print(f"[erro Telegram] {ex}", file=sys.stderr)
        return False


# ------------------------------------------------------------------ processo
def processar(cfg, dry_run=False):
    """Checa e envia lembretes de email (60min) e Telegram (60min)."""
    agora = datetime.now()
    enviados = carregar_enviados()
    novos = 0

    # E-mail: 60 minutos (1 hora) antes
    if "email" in cfg:
        janela_email = agenda.expandir(agenda.carregar(), agora,
                                       agora + timedelta(minutes=ALERTA_EMAIL))
        for occ, e in janela_email:
            chave = f"email|{e['id']}|{occ.isoformat()}"
            if chave in enviados:
                continue
            msg = montar_email(e, occ, cfg["email"])
            if dry_run:
                print("---- (dry-run) e-mail que seria enviado ----------")
                print(f"To: {msg['To']}")
                print(f"Subject: {msg['Subject']}\n")
                print(msg.get_content())
            else:
                enviar_email(msg, cfg["email"])
                print(f"[{agora:%H:%M}] E-mail: '{e['titulo']}' → "
                      f"{msg['To']} ({occ:%H:%M})")
            enviados.add(chave)
            novos += 1

    # Telegram: 60 minutos (1 hora) antes (mesma frequência que e‑mail)
    if "telegram" in cfg:
        janela_tg = agenda.expandir(agenda.carregar(), agora,
                                    agora + timedelta(minutes=ALERTA_TELEGRAM))
        for occ, e in janela_tg:
            chave = f"telegram|{e['id']}|{occ.isoformat()}"
            if chave in enviados:
                continue
            # Usa exatamente o mesmo conteúdo que o e‑mail
            mensagem = montar_mensagem(e, occ)
            if dry_run:
                print("---- (dry-run) Telegram que seria enviado ----------")
                print(f"Chat: {cfg['telegram']['chat_id']}\n")
                print(mensagem)
            else:
                if enviar_telegram(e['titulo'], mensagem, cfg["telegram"]):
                    print(f"[{agora:%H:%M}] Telegram: '{e['titulo']}' → "
                          f"{cfg['telegram']['chat_id']} ({occ:%H:%M})")
                    enviados.add(chave)
                    novos += 1
                else:
                    # falha: nao marca como enviado, sera retentado
                    pass

    if not dry_run:
        salvar_enviados(enviados, agora)
    return novos


# ------------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser(description="Serviço de lembretes (e-mail + Telegram).")
    p.add_argument("--once", action="store_true",
                   help="checa uma vez e sai (para Agendador/cron)")
    p.add_argument("--interval", type=int, default=60,
                   help="segundos entre checagens no modo loop")
    p.add_argument("--dry-run", action="store_true",
                   help="não envia; imprime o que seria enviado")
    p.add_argument("--test", metavar="EMAIL", nargs="?", const="",
                   help="envia um e-mail de teste (usa AGENDA_EMAIL_TO se vazio)")
    p.add_argument("--test-tg", action="store_true",
                   help="envia uma mensagem Telegram de teste")
    p.add_argument("--env", default=str(Path(__file__).with_name(".env")),
                   help="caminho do arquivo .env")
    args = p.parse_args()

    carregar_env(args.env)
    cfg = carregar_config()

    if args.test is not None:
        if "email" not in cfg:
            sys.exit("SMTP não configurado.")
        msg = EmailMessage()
        msg["Subject"] = "✅ Teste — Agenda Simples"
        msg["From"] = cfg["email"]["from"]
        msg["To"] = args.test or cfg["email"]["to"]
        msg.set_content("E-mail de teste do serviço de lembretes da Agenda Simples.\n"
                        "Se você recebeu, o SMTP está configurado corretamente.")
        enviar_email(msg, cfg["email"])
        print(f"E-mail de teste enviado para {msg['To']}.")
        return

    if args.test_tg:
        if "telegram" not in cfg:
            sys.exit("Telegram não configurado.")
        msg = ("✅ Teste — Agenda Simples\n\n"
               "Mensagem de teste do serviço de lembretes.\n"
               "Se você recebeu, o Telegram está configurado corretamente.")
        enviar_telegram("Teste", msg, cfg["telegram"])
        print(f"Mensagem Telegram enviada para {cfg['telegram']['chat_id']}.")
        return

    if args.once:
        n = processar(cfg, args.dry_run)
        print(f"{n} notificação(ões) processada(s).")
        return

    servicos = ", ".join(cfg.keys())
    print(f"Serviço ativo ({servicos}). Checa a cada {args.interval}s. Ctrl+C para sair.")
    try:
        while True:
            try:
                processar(cfg, args.dry_run)
            except Exception as ex:
                print(f"[erro] {ex}", file=sys.stderr)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nServiço encerrado.")


if __name__ == "__main__":
    main()
