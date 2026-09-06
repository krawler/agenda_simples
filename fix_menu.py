#!/usr/bin/env python3
"""
Script para corrigir o menu dropdown refatorando as funções para escopo global
"""

import re

file_path = r'c:\Users\Usuario\kepler\repositories\agenda_simples\templates\renderers\page.html'

# Ler o arquivo
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Padrão a encontrar (início da IIFE do menu)
old_pattern = r'''  // View Menu Dropdown Handler
  \(function \(\) \{
    const menuTrigger = document\.getElementById\('menu-trigger'\);
    const viewMenu = document\.getElementById\('view-menu'\);
    let menuOpenTimeout = null;'''

# Novo código (funções globais primeiro)
new_prefix = '''  // Definir funcoes globais PRIMEIRO
  window.trocarView = function (view) {
    console.log('[MENU] Trocando view:', view);
    const date = new Date().toISOString().slice(0, 10);
    const calendar = document.getElementById('calendar');
    const dayPanel = document.getElementById('day-panel');

    if (view === 'day') {
      if (calendar) calendar.style.display = 'none';
      if (dayPanel) dayPanel.style.display = '';
      document.body.dataset.editMode = 'false';
      return;
    }

    document.body.dataset.editMode = 'false';
    if (calendar) calendar.style.display = '';
    if (dayPanel) dayPanel.style.display = 'none';

    if (window.htmx) {
      htmx.ajax('GET', '/agenda?view=' + encodeURIComponent(view) + '&date=' + encodeURIComponent(date), {
        target: '#calendar',
        swap: 'outerHTML'
      });
    } else {
      window.location.href = '/agenda?view=' + encodeURIComponent(view) + '&date=' + encodeURIComponent(date);
    }
  };

  window.abrirConfig = function () {
    console.log('[MENU] Abrindo config');
    const configModal = document.getElementById('config-modal');
    if (configModal && typeof configModal.showModal === 'function') {
      configModal.showModal();
    }
  };

  // View Menu Dropdown Handler
  (function () {
    const menuTrigger = document.getElementById('menu-trigger');
    const viewMenu = document.getElementById('view-menu');
    let menuOpenTimeout = null;'''

# Procurar por "if (view)" dentro da IIFE e remover as definições internas de trocarView e abrirConfig
# Remover essas linhas depois do forEach do menuItems

pattern_remove_internal_functions = r'''

    window\.trocarView = function \(view\) \{
      const date = new Date\(\)\.toISOString\(\)\.slice\(0, 10\);
      const calendar = document\.getElementById\('calendar'\);
      const dayPanel = document\.getElementById\('day-panel'\);

      if \(view === 'day'\) \{
        if \(calendar\) calendar\.style\.display = 'none';
        if \(dayPanel\) dayPanel\.style\.display = '';
        document\.body\.dataset\.editMode = 'false';
        return;
      \}

      document\.body\.dataset\.editMode = 'false';
      if \(calendar\) calendar\.style\.display = '';
      if \(dayPanel\) dayPanel\.style\.display = 'none';

      if \(window\.htmx\) \{
        htmx\.ajax\('GET', '/agenda\?view=' \+ encodeURIComponent\(view\) \+ '&date=' \+ encodeURIComponent\(date\), \{
          target: '#calendar',
          swap: 'outerHTML'
        \}\);
      \} else \{
        window\.location\.href = '/agenda\?view=' \+ encodeURIComponent\(view\) \+ '&date=' \+ encodeURIComponent\(date\);
      \}
    \};

    window\.abrirConfig = function \(\) \{
      const configModal = document\.getElementById\('config-modal'\);
      if \(configModal && typeof configModal\.showModal === 'function'\) \{
        configModal\.showModal\(\);
      \}
    \};'''

# Fazer a substituição
if re.search(old_pattern, content):
    print("✅ Padrão encontrado! Fazendo substituição...")
    content = re.sub(old_pattern, new_prefix, content)
    
    # Remover as definições internas se existirem
    content = re.sub(pattern_remove_internal_functions, '', content, flags=re.DOTALL)
    
    # Salvar o arquivo
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Arquivo atualizado com sucesso!")
else:
    print("❌ Padrão não encontrado no arquivo")
    print("\nProcurando pelo conteúdo atual...")
    if '// View Menu Dropdown Handler' in content:
        print("✅ Encontrei '// View Menu Dropdown Handler'")
        # Mostrar as próximas 200 caracteres
        idx = content.find('// View Menu Dropdown Handler')
        print(content[idx:idx+300])
