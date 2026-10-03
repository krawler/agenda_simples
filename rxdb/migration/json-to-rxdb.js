import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');

function resolverCaminhoEventosLegado() {
  const caminhoNovo = path.join(PROJECT_ROOT, 'data', 'eventos.json');
  const caminhoAntigo = path.join(PROJECT_ROOT, 'eventos.json');

  if (fs.existsSync(caminhoNovo)) {
    return caminhoNovo;
  }

  if (fs.existsSync(caminhoAntigo)) {
    return caminhoAntigo;
  }

  throw new Error('Arquivo de eventos legado não encontrado em data/eventos.json nem em eventos.json.');
}

function normalizarRecorrencia(evento = {}) {
  const recorrencia = evento.recorrencia ?? {};
  const diasSemana = Array.isArray(recorrencia.diasSemana ?? evento.diasSemana)
    ? (recorrencia.diasSemana ?? evento.diasSemana)
    : [];

  return {
    tipo: String(recorrencia.tipo ?? evento.repeat ?? 'none'),
    until: String(recorrencia.until ?? evento.until ?? ''),
    diasSemana: diasSemana.map((valor) => Number(valor))
  };
}

function normalizarEventoJson(evento, index) {
  const agora = new Date().toISOString();

  return {
    id: String(evento.id ?? `evt_${index + 1}`),
    titulo: String(evento.titulo ?? 'Sem título'),
    inicio: evento.inicio ?? evento.inicio_iso ?? new Date().toISOString(),
    duracaoMinutos: Number(evento.dur ?? evento.duracaoMinutos ?? 0),
    descricao: String(evento.desc ?? evento.descricao ?? ''),
    except: Array.isArray(evento.except) ? evento.except : [],
    recorrencia: normalizarRecorrencia(evento),
    status: String(evento.status ?? 'ativo'),
    cancelado: Boolean(evento.cancelado ?? false),
    concluido: Boolean(evento.concluido ?? false),
    userId: String(evento.userId ?? 'local-user'),
    removido: Boolean(evento.deleted ?? evento.removido ?? false),
    createdAt: evento.createdAt ?? agora,
    updatedAt: evento.updatedAt ?? agora
  };
}

function carregarEventosLegado(jsonPath) {
  const resolvedPath = path.resolve(jsonPath ?? resolverCaminhoEventosLegado());
  const raw = fs.readFileSync(resolvedPath, 'utf-8');
  const lista = JSON.parse(raw);

  if (!Array.isArray(lista)) {
    throw new Error('O JSON de origem precisa ser uma lista de eventos.');
  }

  return lista.map(normalizarEventoJson);
}

async function migrarJsonParaRxdb(jsonPath, collection) {
  const documentos = carregarEventosLegado(jsonPath);

  if (!collection || typeof collection.bulkUpsert !== 'function') {
    throw new Error('Coleção RxDB inválida para a migração.');
  }

  await collection.bulkUpsert(documentos);
  return documentos;
}

export {
  normalizarEventoJson,
  normalizarRecorrencia,
  carregarEventosLegado,
  migrarJsonParaRxdb,
  resolverCaminhoEventosLegado
};
