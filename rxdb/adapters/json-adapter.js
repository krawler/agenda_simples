import fs from 'node:fs';
import path from 'node:path';
import { normalizarEventoJson, resolverCaminhoEventosLegado } from '../migration/json-to-rxdb.js';

function carregarEventosJson(filePath) {
  const resolved = path.resolve(filePath ?? resolverCaminhoEventosLegado());

  if (!fs.existsSync(resolved)) {
    return [];
  }

  const raw = fs.readFileSync(resolved, 'utf-8');
  const parsed = JSON.parse(raw);

  if (!Array.isArray(parsed)) {
    throw new Error('Arquivo de eventos inválido: esperado uma lista JSON.');
  }

  return parsed;
}

function salvarEventosJson(filePath, eventos) {
  const resolved = path.resolve(filePath);
  const dir = path.dirname(resolved);

  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  fs.writeFileSync(resolved, JSON.stringify(eventos, null, 2), 'utf-8');
  return resolved;
}

function adapterEventosParaRxdb(eventos) {
  return eventos.map((evento, index) => normalizarEventoJson(evento, index));
}

export { carregarEventosJson, salvarEventosJson, adapterEventosParaRxdb };
