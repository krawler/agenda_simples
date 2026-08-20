Teste E2E e diagnóstico - `agenda_simples` scripts

Este diretório contém utilitários para diagnóstico e testes.

Playwright E2E (valida pop-up de sincronização com erros)

Pré-requisitos:

- Python 3.10+
- Instale Playwright e baixe navegadores:

```bash
pip install playwright
python -m playwright install
```

Executar o teste (headless):

```bash
python scripts/run_live_sync_test.py --run-playwright
```

Observações:

- O teste inicia o servidor localmente em `127.0.0.1:8008` e injeta uma simulação de erro em `agenda.sync_all_with_progress`.
- O script imprime o conteúdo do painel de status `#sync-status` e o modal `#sync-details-content`.
- Para rodar manualmente o teste diretamente:

```bash
python scripts/test_sync_popup_playwright.py
```
