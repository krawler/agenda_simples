import { carregarEventosJson, salvarEventosJson } from '../adapters/json-adapter.js';
import { createRxDbRepository } from '../adapters/rxdb-adapter.js';

function criarEventoService({ filePath, collection } = {}) {
  const repo = createRxDbRepository({ collection });

  return {
    async listar() {
      return carregarEventosJson(filePath);
    },

    async salvar(eventos) {
      if (!filePath) {
        return eventos;
      }

      salvarEventosJson(filePath, eventos);
      return eventos;
    },

    async migrarParaRxdb() {
      const eventos = carregarEventosJson(filePath);
      return repo.bulkInsert(eventos);
    }
  };
}

export { criarEventoService };
