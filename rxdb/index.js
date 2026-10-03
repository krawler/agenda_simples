export { createDatabase, createEventosCollection } from './collections/index.js';
export { rxdbSchemas } from './schemas/index.js';
export {
  migrarJsonParaRxdb,
  normalizarEventoJson,
  carregarEventosLegado,
  resolverCaminhoEventosLegado
} from './migration/json-to-rxdb.js';
export { createEventosReplication } from './sync/firestore-replication.js';
