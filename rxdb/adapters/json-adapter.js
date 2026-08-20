const fs = require('fs');
const path = require('path');
const { normalizarEventoJson } = require('../migration/json-to-rxdb');

function carregarEventosJson(filePath) {
  const resolved = path.resolve(filePath);

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

module.exports = {
  carregarEventosJson,
  salvarEventosJson,
  adapterEventosParaRxdb
};
