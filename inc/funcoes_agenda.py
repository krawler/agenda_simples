#!/usr/bin/env python3
"""Funções auxiliares da agenda, extraídas de server.py."""

import calendar as calmod
import os
import subprocess
import signal
from datetime import date, datetime, time, timedelta
from pathlib import Path

import agenda


def eventos_do_dia(d):
    wstart = datetime.combine(d, time.min)
    wend = datetime.combine(d, time.max)
    return agenda.expandir(agenda.carregar(), wstart, wend)


def dias_com_eventos(ano, mes):
    ultimo = calmod.monthrange(ano, mes)[1]
    wstart = datetime.combine(date(ano, mes, 1), time.min)
    wend = datetime.combine(date(ano, mes, ultimo), time.max)
    return {occ.date() for occ, _ in agenda.expandir(agenda.carregar(), wstart, wend)}


def ler_pid_do_arquivo():
    """Lê o PID do arquivo .agenda_server.pid."""
    try:
        pid_file = Path(__file__).resolve().parent.parent / ".agenda_server.pid"
        if pid_file.exists():
            return int(pid_file.read_text().strip())
    except (ValueError, IOError):
        pass
    return None


def encerrar_processo_por_pid(pid):
    """Encerra o processo com o PID especificado."""
    try:
        if os.name == "nt":
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        else:
            os.kill(pid, signal.SIGTERM)
            return True
    except Exception:
        return False


def salvar_pid_em_arquivo():
    """Salva o PID atual no arquivo .agenda_server.pid."""
    try:
        pid_file = Path(__file__).resolve().parent.parent / ".agenda_server.pid"
        pid_file.write_text(str(os.getpid()))
    except Exception:
        pass


def remover_pid_arquivo_se_for_deste_processo():
    """Remove o arquivo PID se ele pertencer a este processo."""
    try:
        pid_file = Path(__file__).resolve().parent.parent / ".agenda_server.pid"
        if pid_file.exists():
            pid_arquivo = int(pid_file.read_text().strip())
            if pid_arquivo == os.getpid():
                pid_file.unlink()
    except (ValueError, IOError):
        pass


# Teste básico para verificar se está funcionando
if __name__ == "__main__":
    print("Teste: eventos_do_dia para hoje")
    hoje = date.today()
    eventos = eventos_do_dia(hoje)
    print(f"  Eventos hoje ({hoje}): {len(eventos)}")
    print("Teste: dias_com_eventos")
    dias = dias_com_eventos(hoje.year, hoje.month)
    print(f"  Dias com eventos neste mês: {len(dias)}")
    print("Funções importadas com sucesso.")
