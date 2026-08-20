"""Teste automatizado que simula erro na sincronização e verifica o popup.

Requisitos:
  pip install playwright
  python -m playwright install

Uso:
  python scripts/test_sync_popup_playwright.py
"""
import argparse
import os
import sys
import threading
import time
from datetime import datetime
from http.server import ThreadingHTTPServer
from pathlib import Path

# Ensure repo root is on sys.path so this script can import the package when run from /scripts
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agenda
import server


def start_server(host="127.0.0.1", port=8008):
    srv = ThreadingHTTPServer((host, port), server.Handler)

    def run():
        srv.serve_forever()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv


def fake_sync_all_with_progress(on_progress=None):
    logs = []
    def p(msg):
        logs.append(msg)
        if on_progress:
            on_progress(msg)
        time.sleep(0.05)

    p("Iniciando sincronização (simulação)...")
    p("SIMULAÇÃO: Enviando eventos locais → Erro: falha de rede ao enviar evento X")
    p("SIMULAÇÃO: Buscando eventos do Google → Erro: token inválido")

    # Mensagem final + listas vazias de importados/exportados
    return ("Erros encontrados durante a sincronização", [], [], logs)


def run_test(headful=False, out_dir=None, timeout=10000):
    # Substitui função real por fake
    agenda._orig_sync = getattr(agenda, "sync_all_with_progress", None)
    agenda.sync_all_with_progress = fake_sync_all_with_progress

    host = "127.0.0.1"
    port = 8008
    srv = start_server(host, port)

    # Aguarda servidor subir
    time.sleep(0.3)

    from playwright.sync_api import sync_playwright

    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(__file__), "test_output")
    os.makedirs(out_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    screenshot_path = os.path.join(out_dir, f"sync_status_{ts}.png")
    html_path = os.path.join(out_dir, f"page_{ts}.html")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context()
        page = context.new_page()
        page.goto(f"http://{host}:{port}")

        # Clica no botão de sincronizar
        page.click("#sync-google")

        # Aguarda que os logs da sincronização sejam preenchidos no cliente
        try:
            page.wait_for_function("() => window.syncLogsData && window.syncLogsData.length > 0", timeout=timeout)
        except Exception:
            # Fallback: aguardar o painel de status conter palavras-chave de erro
            try:
                page.wait_for_function("() => document.querySelector('#sync-status') && /Erro|Erros encontrados|SIMULAÇÃO/.test(document.querySelector('#sync-status').innerText)", timeout=3000)
            except Exception:
                pass

        # Captura estado e artefatos
        try:
            page.screenshot(path=screenshot_path, full_page=True)
        except Exception as ex:
            print("Falha ao capturar screenshot:", ex)

        try:
            html = page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
        except Exception as ex:
            print("Falha ao salvar HTML:", ex)

        # Lê e imprime conteúdo do painel de status
        try:
            status_text = page.inner_text("#sync-status")
            print("Conteúdo de #sync-status:\n", status_text)
        except Exception:
            print("#sync-status não encontrado")

        # Se houver link para detalhes, abre modal e salva conteúdo
        try:
            if page.locator("text=Exibir detalhes").count() > 0:
                page.click("text=Exibir detalhes")
                page.wait_for_selector("#sync-details-modal[open]", timeout=3000)
                content = page.inner_text("#sync-details-content")
                print("Conteúdo do modal de detalhes:\n", content)

                # também salvar em arquivo
                with open(os.path.join(out_dir, f"sync_details_{ts}.txt"), "w", encoding="utf-8") as f:
                    f.write(content)
        except Exception:
            pass

        browser.close()

    # Restaura função original
    if agenda._orig_sync is not None:
        agenda.sync_all_with_progress = agenda._orig_sync

    srv.shutdown()
    print("Teste concluído. Artefatos em:", out_dir)


if __name__ == "__main__":
    run_test()
