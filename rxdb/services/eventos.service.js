const { carregarEventosJson, salvarEventosJson } = require('../adapters/json-adapter');
const { createRxDbRepository } = require('../adapters/rxdb-adapter');

function criarEventoService({ filePath, collection } = {}) {
  const repo = createRxDbRepository({ collection });

  return {
    async listar() {
      const eventos = carregarEventosJson(filePath || 'eventos.json');
      return eventos;
    },

    async salvar(eventos) {
      if (!filePath) {
        return eventos;
      }

      salvarEventosJson(filePath, eventos);
      return eventos;
    },

    async migrarParaRxdb() {
      const eventos = carregarEventosJson(filePath || 'eventos.json');
      return repo.bulkInsert(eventos);
    }
  };
}

module.exports = {
  criarEventoService
};
