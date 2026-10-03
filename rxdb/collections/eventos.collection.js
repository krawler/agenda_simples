import { addRxPlugin, createRxDatabase } from 'rxdb/plugins/core';
import { RxDBDevModePlugin } from 'rxdb/plugins/dev-mode';
import { getRxStorageMemory } from 'rxdb/plugins/storage-memory';
import { wrappedValidateAjvStorage } from 'rxdb/plugins/validate-ajv';
import { rxdbSchemas } from '../schemas/index.js';

let devModeLoaded = false;

function ensureDevMode() {
  // Node não tem storage persistente por padrão; memory-storage é usada
  // pelos scripts de migração/sincronização (o app web usará Dexie no navegador).
  if (!devModeLoaded) {
    addRxPlugin(RxDBDevModePlugin);
    devModeLoaded = true;
  }
}

async function createEventosCollection(db) {
  const collections = await db.addCollections({
    eventos: {
      schema: rxdbSchemas.eventos
    }
  });
  return collections.eventos;
}

async function createDatabase(name = 'agenda_simples_rxdb') {
  ensureDevMode();

  const db = await createRxDatabase({
    name,
    storage: wrappedValidateAjvStorage({ storage: getRxStorageMemory() })
  });

  await createEventosCollection(db);
  return db;
}

export { createDatabase, createEventosCollection };
