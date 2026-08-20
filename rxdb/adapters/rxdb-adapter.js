const { adapterEventosParaRxdb } = require('./json-adapter');

function createRxDbRepository({ collection, logger = console }) {
  return {
    async listAll() {
      if (!collection) {
        return [];
      }

      if (typeof collection.find === 'function') {
        return collection.find().exec();
      }

      if (typeof collection.getAll === 'function') {
        return collection.getAll();
      }

      return [];
    },

    async upsert(evento) {
      if (!collection) {
        logger.warn('Coleção RxDB não inicializada. Operação ignorada.');
        return evento;
      }

      if (typeof collection.upsert === 'function') {
        return collection.upsert(evento);
      }

      if (typeof collection.insert === 'function') {
        return collection.insert(evento);
      }

      return evento;
    },

    async bulkInsert(eventos) {
      if (!collection) {
        logger.warn('Coleção RxDB não inicializada. Nenhum dado foi importado.');
        return [];
      }

      const normalized = adapterEventosParaRxdb(eventos);

      if (typeof collection.bulkInsert === 'function') {
        await collection.bulkInsert(normalized);
      }

      return normalized;
    },

    async syncFromLegacyJson(filePath) {
      const { carregarEventosJson } = require('./json-adapter');
      const eventos = carregarEventosJson(filePath);
      return this.bulkInsert(eventos);
    }
  };
}

module.exports = {
  createRxDbRepository
};
