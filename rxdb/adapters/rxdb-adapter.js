import { adapterEventosParaRxdb } from './json-adapter.js';
import { carregarEventosJson } from './json-adapter.js';

function createRxDbRepository({ collection, logger = console }) {
  return {
    async listAll() {
      if (!collection) {
        return [];
      }

      if (typeof collection.find === 'function') {
        return collection.find().exec();
      }

      return [];
    },

    async upsert(evento) {
      if (!collection) {
        logger.warn('Coleção RxDB não inicializada. Operação ignorada.');
        return evento;
      }

      return collection.incrementalUpsert(evento);
    },

    async bulkInsert(eventos) {
      if (!collection) {
        logger.warn('Coleção RxDB não inicializada. Nenhum dado foi importado.');
        return [];
      }

      const normalized = adapterEventosParaRxdb(eventos);
      await collection.bulkUpsert(normalized);
      return normalized;
    },

    async syncFromLegacyJson(filePath) {
      const eventos = carregarEventosJson(filePath);
      return this.bulkInsert(eventos);
    }
  };
}

export { createRxDbRepository };
