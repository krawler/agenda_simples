import { createDatabase } from '../rxdb/collections/index.js';
import { carregarEventosLegado, resolverCaminhoEventosLegado } from '../rxdb/migration/json-to-rxdb.js';
import { createEventosReplication } from '../rxdb/sync/firestore-replication.js';
import { db as firestoreDb } from '../firebase/config.js';

/**
 * Migra os eventos legados (data/eventos.json) para o RxDB local
 * e replica para o Firestore. Nao toca em agenda.py/server.py:
 * eles continuam sendo os unicos donos de leitura/escrita do JSON.
 */
async function main() {
  const caminhoJson = resolverCaminhoEventosLegado();
  console.log(`Lendo eventos legados de: ${caminhoJson}`);

  const eventos = carregarEventosLegado(caminhoJson);
  console.log(`${eventos.length} evento(s) normalizado(s) a partir do JSON legado.`);

  const rxdb = await createDatabase('agenda_simples_migracao');
  await rxdb.eventos.bulkUpsert(eventos);
  console.log(`${eventos.length} evento(s) gravado(s) no RxDB local (memoria).`);

  const replicationState = createEventosReplication({
    firestoreDb,
    rxCollection: rxdb.eventos,
    live: false
  });

  replicationState.error$.subscribe((error) => {
    console.error('Erro na replicacao com o Firestore:', error);
  });

  await replicationState.awaitInitialReplication();
  console.log('Replicacao inicial para o Firestore concluida.');

  await replicationState.cancel();
  await rxdb.close();
  console.log('Migracao finalizada com sucesso.');
}

main().catch((error) => {
  console.error('Falha na migracao dos eventos:', error);
  process.exitCode = 1;
});
