const { addRxPlugin, createRxDatabase } = require('rxdb');
const { RxDBDevModePlugin } = require('rxdb/plugins/dev-mode');
const { getRxStorageDexie } = require('rxdb/plugins/storage-dexie');
const { rxdbSchemas } = require('../schemas');

addRxPlugin(RxDBDevModePlugin);

async function createEventosCollection(db) {
  return db.addCollections({
    eventos: {
      schema: rxdbSchemas.eventos
    }
  });
}

async function createDatabase(name = 'agenda_simples_rxdb') {
  const db = await createRxDatabase({
    name,
    storage: getRxStorageDexie()
  });

  await createEventosCollection(db);
  return db;
}

module.exports = {
  createDatabase,
  createEventosCollection
};
