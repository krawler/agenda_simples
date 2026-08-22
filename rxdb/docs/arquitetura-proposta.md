# Proposta de arquitetura para RxDB + Firebase

## Objetivo
Manter o funcionamento atual da agenda, desacoplando a persistência em JSON do restante da aplicação e introduzindo uma camada local reativa com RxDB. A sincronização em nuvem será tratada por Firebase, sem bloquear o uso do app tradicional.

## Princípios
- responsabilidade única por módulo
- isolamento da camada de persistência
- compatibilidade com o código legado
- migração incremental
- menor impacto possível no funcionamento da aplicação atual

## Estrutura de arquivos sugerida

```text
rxdb/
  index.js
  collections/
    index.js
    eventos.collection.js
  schemas/
    index.js
    eventos.schema.js
    ocorrencias.schema.js
    lembretes.schema.js
    sync-meta.schema.js
  migration/
    json-to-rxdb.js
  sync/
    firebase-sync.js
  services/
    eventos.service.js
    recorrencia.service.js
    notificacao.service.js
  adapters/
    json-adapter.js
    rxdb-adapter.js
```

## Módulos e responsabilidades

### rxdb/collections
Cria e inicializa as coleções RxDB.

### rxdb/schemas
Define o contrato dos documentos.

### rxdb/migration
Converte JSON atual em documentos RxDB.

### rxdb/sync
Gerencia sincronização com Firebase.

### rxdb/services
Contém serviços de domínio, como eventos, recorrência e lembretes.

### rxdb/adapters
Converte o padrão antigo para o novo sem quebrar a lógica existente.

## Fluxo sugerido

1. O sistema legado continua lendo JSON.
2. Um adaptador novo usa RxDB para leitura/escrita local.
3. O script de migração converte o JSON antigo para documento do RxDB.
4. A sincronização com Firebase apenas replica dados já validados.
5. A lógica do calendário continua sendo reusada, mas o acesso à persistência fica isolado.

## Estratégia de migração
- importar o JSON atual
- converter os campos para o schema do RxDB
- manter tabela de mapeamento dos IDs antigos
- validar no ambiente de teste
- ativar sincronização em nuvem em seguida

## Observação de compatibilidade
A implantação deve ser gradual:
- primeiro criar a camada RxDB sem remover o JSON
- depois migrar os reads/writes
- depois remover o código antigo quando os testes confirmarem

## Resultado esperado
A aplicação ganha:
- armazenamento local reativo
- sincronização remota segura
- menor acoplamento
- menos risco para o código legado
