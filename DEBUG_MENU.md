# Debug: Menu Dropdown Não Funciona

## 🔴 Problema Identificado

As funções `trocarView()` e `abrirConfig()` estão **dentro de uma função auto-executável (IIFE)**, o que as torna inacessíveis globalmente quando clicadas.

## ✅ Solução

Vou refatorar o código para:
1. Definir as funções no escopo global (`window.`)
2. Inicializar os event listeners quando o DOM estiver pronto
3. Adicionar logs de debug para rastrear o que está acontecendo

## 🔧 Passos para Testar

### 1. **Limpar Cache do Navegador**
- **Chrome/Edge**: `Ctrl + Shift + Delete` → Limpar dados em navegação → **Cookies e dados de site** + **Cache**
- **Firefox**: `Ctrl + Shift + Delete` → Verificar "Cache"
- Ou simplesmente: `Ctrl + Shift + R` (hard refresh)

### 2. **Abrir o Console (F12)**
Você deve ver logs como:
```
[Menu] Inicializando dropdown
[Menu] Encontrados 4 itens do menu
[Menu] Clicado item 0 - view: day
[Menu] Trocando view para: day
```

### 3. **Testar Cada Funcionalidade**
- Abra a página
- Passe o mouse sobre o ícone do menu (3 linhas)
- Menu deve aparecer com animação
- Clique em "Dia" → console deve mostrar logs
- Clique em "Semana" → deve carregar a view
- Clique em "Mês" → deve carregar a view
- Clique em "Configurações" → deve abrir o modal

## 🐛 Se Ainda Não Funcionar

1. Pressione **F12** para abrir o DevTools
2. Vá até a aba **Console**
3. Execute: `console.log(window.trocarView)` - deve mostrar a função
4. Execute: `window.trocarView('day')` - deve funcionar manualmente
5. Procure por erros em vermelho na console

## 📝 Logs Esperados na Console

```javascript
[Menu] Inicializando dropdown
[Menu] Encontrados 4 itens do menu
[Menu] Menu aberto
[Menu] Clicado item 0 - view: day
[Menu] Trocando view para: day
[Menu] Alternando para view de dia
[Menu] Menu fechado
```

## 🚀 Próximas Ações

Vou aplicar a refatoração agora para corrigir o escopo das funções!
