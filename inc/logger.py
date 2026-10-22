import logging
import functools
import traceback

# Configuração do logger em console
def setup_logger(name="agenda_app", level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)

    logger.propagate = False
    return logger


LOGGER = setup_logger()


def log_console(level, mensagem, **dados):
    if dados:
        mensagem = f"{mensagem} | " + " | ".join(f"{k}={v}" for k, v in dados.items())
    if level == "DEBUG":
        LOGGER.debug(mensagem)
    elif level == "INFO":
        LOGGER.info(mensagem)
    elif level == "WARNING":
        LOGGER.warning(mensagem)
    elif level == "ERROR":
        LOGGER.error(mensagem)
    else:
        LOGGER.info(mensagem)


def tratar_excecao(exc, contexto="Operação"):
    LOGGER.exception("Erro em %s: %s", contexto, exc)
    print(f"\n[ERRO] {contexto}: {type(exc).__name__}: {exc}")
    traceback.print_exc()


def capturar_excecoes(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            log_console("INFO", f"Iniciando: {func.__name__}")
            return func(*args, **kwargs)
        except Exception as exc:
            tratar_excecao(exc, f"função {func.__name__}")
            return None  # ou raise se quiser quebrar a aplicação de forma explícita
    return wrapper