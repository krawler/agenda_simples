const fs = require('fs');
const path = require('path');

function normalizarEventoJson(evento, index) {
  const agora = new Date().toISOString();

  return {
    id: String(evento.id ?? `evt_${index + 1}`),
    titulo: String(evento.titulo ?? 'Sem título'),
    inicio: evento.inicio ?? evento.inicio_iso ?? new Date().toISOString(),
    duracaoMinutos: Number(evento.dur ?? 0),
    descricao: evento.desc ?? '',
    except: Array.isArray(evento.except) ? evento.except : [],
    recorrencia: {
      tipo: evento.repeat ?? 'none',
      until: evento.until ?? '',
      diasSemana: Array.isArray(evento.diasSemana) ? evento.diasSemana : []
    },
    status: evento.status ?? 'ativo',
    cancelado: Boolean(evento.cancelado),
    concluido: Boolean(evento.concluido),
    userId: evento.userId ?? 'local-user',
    deleted: Boolean(evento.deleted),
    createdAt: evento.createdAt ?? agora,
    updatedAt: evento.updatedAt ?? agora
  };
}

async function migrarJsonParaRxdb(jsonPath, collection) {
  const resolvedPath = path.resolve(jsonPath);
  const raw = fs.readFileSync(resolvedPath, 'utf-8');
  const lista = JSON.parse(raw);

  if (!Array.isArray(lista)) {
    throw new Error('O JSON de origem precisa ser uma lista de eventos.');
  }

  const documentos = lista.map(normalizarEventoJson);

  if (!collection || typeof collection.bulkInsert !== 'function') {
    throw new Error('Coleção RxDB inválida para a migração.');
  }

  await collection.bulkInsert(documentos);
  return documentos;
}

module.exports = {
  normalizarEventoJson,
  migrarJsonParaRxdb
};
