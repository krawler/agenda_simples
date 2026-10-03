import fs from 'node:fs';
import { createDatabase } from '../rxdb/collections/index.js';
import { carregarEventosLegado, resolverCaminhoEventosLegado } from '../rxdb/migration/json-to-rxdb.js';
import { createEventosReplication } from '../rxdb/sync/firestore-replication.js';
import { db as firestoreDb } from '../firebase/config.js';

const DEBOUNCE_MS = 800;

/**
 * Observa data/eventos.json (fonte de verdade de agenda.py/server.py) e espelha
 * as mudancas para o Firestore via RxDB. Nunca escreve no JSON: e apenas leitura.
 */
async function main() {
  const caminhoJson = resolverCaminhoEventosLegado();
  console.log(`Observando alteracoes em: ${caminhoJson}`);

  const rxdb = await createDatabase('agenda_simples_watch_sync');
  const replicationState = createEventosReplication({
    firestoreDb,
    rxCollection: rxdb.eventos,
    live: true
  });

  async function sincronizarAgora() {
    try {
      const eventos = carregarEventosLegado(caminhoJson);
      await rxdb.eventos.bulkUpsert(eventos);
      console.log(`[${new Date().toISOString()}] ${eventos.length} evento(s) sincronizado(s).`);
    } catch (error) {
      console.error('Erro ao sincronizar eventos:', error.message);
    }
  }

  await sincronizarAgora();

  let timeoutId = null;
  fs.watch(caminhoJson, { persistent: true }, () => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(sincronizarAgora, DEBOUNCE_MS);
  });

  process.on('SIGINT', async () => {
    console.log('Encerrando sincronizacao...');
    await replicationState.cancel();
    await rxdb.close();
    process.exit(0);
  });

  console.log('Sincronizacao ativa. Pressione Ctrl+C para encerrar.');
}

main().catch((error) => {
  console.error('Falha ao iniciar a sincronizacao:', error);
  process.exitCode = 1;
});
