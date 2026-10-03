import { replicateFirestore } from 'rxdb/plugins/replication-firestore';
import { collection as firestoreCollectionRef } from 'firebase/firestore';

/**
 * Cria a replicacao ao vivo entre a colecao local `eventos` (RxDB)
 * e a colecao remota `eventos` no Firestore.
 */
function createEventosReplication({ firestoreDb, rxCollection, live = true }) {
  if (!firestoreDb || !rxCollection) {
    throw new Error('firestoreDb e rxCollection sao obrigatorios para a replicacao.');
  }

  return replicateFirestore({
    replicationIdentifier: 'agenda-simples-eventos-firestore-v2',
    collection: rxCollection,
    firestore: {
      database: firestoreDb,
      collection: firestoreCollectionRef(firestoreDb, 'eventos')
    },
    pull: {},
    push: {},
    live,
    retryTime: 5000
  });
}

export { createEventosReplication };
