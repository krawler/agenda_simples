#!/usr/bin/env python3
"""
Script para adicionar window. prefix aos calls de funcoes globais
"""

file_path = r'c:\Users\Usuario\kepler\repositories\agenda_simples\templates\renderers\page.html'

# Ler o arquivo
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Substituir trocarView(view) por window.trocarView(view)
content = content.replace('          trocarView(view);', '          window.trocarView(view);')

# Substituir abrirConfig() por window.abrirConfig()
content = content.replace('          abrirConfig();', '          window.abrirConfig();')

# Salvar o arquivo
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Arquivo atualizado com window. prefix!")
