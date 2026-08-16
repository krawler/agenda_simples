## Plan: Corrigir Overlay Travando a Pagina

Corrigir o fechamento do modal de configuracoes para usar a API nativa de dialog (close), eliminando o estado invisivel porem aberto que mantem o backdrop bloqueando cliques na tela principal. O foco e ajuste pontual no JavaScript de fechamento, sem mexer no layout.

**Steps**
1. Confirmar no codigo o caminho de fechamento atual do botao com classe close-btn e mapear todos os pontos que usam data-close-target. Base para as proximas mudancas.
2. Alterar o handler initCloseButtons para, ao detectar um elemento dialog, chamar dialog.close() em vez de aplicar ocultacao via CSS/jQuery (hide). Depends on 1.
3. Manter fallback seguro para elementos nao-dialog (ex.: alerts/banners) com hide, para nao quebrar outros botoes de fechar existentes. Depends on 2.
4. Opcional defensivo: no abrirConfig, garantir estado consistente chamando close se necessario antes de showModal quando o browser reportar estado incoerente. Parallel with 3, only if needed after test.
5. Revisar no template de configuracoes se o botao X (data-close-target="config-modal") continua apontando para o id correto e sem manipulacoes concorrentes. Depends on 2.
6. Validar funcionamento manual dos 4 caminhos de fechamento (X, Salvar, Cancelar, clique no backdrop). Depends on 2, 3, 5.

**Relevant files**
- c:/Users/Usuario/kepler/repositories/agenda_simples/server.py - atualizar initCloseButtons e, se necessario, abrirConfig no script embutido da pagina.
- c:/Users/Usuario/kepler/repositories/agenda_simples/templates/config.htm - conferir alvo do botao X e compatibilidade com fechamento via dialog.close().

**Verification**
1. Abrir modal de configuracoes e fechar pelo botao X; confirmar que a pagina principal permanece clicavel.
2. Abrir e fechar via botao Cancelar; confirmar ausencia de bloqueio.
3. Abrir e fechar via Salvar; confirmar ausencia de bloqueio.
4. Abrir e fechar clicando no backdrop; confirmar ausencia de bloqueio.
5. Repetir ciclo 10+ vezes para validar estabilidade intermitente relatada (quase todas as vezes).
6. Verificar em DevTools que apos fechamento o dialog#config-modal nao permanece com estado open.

**Decisions**
- Incluido: correcao especifica de fechamento de modal e regressao dos botoes de close ja existentes.
- Excluido: mudancas visuais de UI/UX e refatoracoes amplas de JavaScript nao relacionadas ao travamento.
- Decisao tecnica: priorizar API nativa de dialog para semantica correta do backdrop.

**Further Considerations**
1. Se houver outros modais futuros, padronizar helper unico closeTargetElement(targetId) para evitar regressao.
2. Se o navegador alvo incluir versoes antigas sem suporte consistente a dialog, considerar polyfill dedicado.
