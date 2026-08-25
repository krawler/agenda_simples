"""Funções utilitárias compartilhadas pelo servidor web."""

import os
import signal
from pathlib import Path


PID_FILE = Path(__file__).resolve().parents[1] / ".agenda_server.pid"


def ler_pid_do_arquivo():
	try:
		return int(PID_FILE.read_text(encoding="utf-8").strip())
	except Exception:
		return None


def encerrar_processo_por_pid(pid):
	try:
		if os.name == "nt":
			os.kill(pid, signal.CTRL_BREAK_EVENT)
		else:
			os.kill(pid, signal.SIGTERM)
		return True
	except Exception:
		return False


def salvar_pid_em_arquivo():
	PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def remover_pid_arquivo_se_for_deste_processo():
	try:
		if PID_FILE.exists() and PID_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
			PID_FILE.unlink()
	except Exception:
		pass
