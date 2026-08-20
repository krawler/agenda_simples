const { createDatabase } = require('./collections');
const { rxdbSchemas } = require('./schemas');
const { migrarJsonParaRxdb, normalizarEventoJson } = require('./migration/json-to-rxdb');

module.exports = {
  createDatabase,
  rxdbSchemas,
  migrarJsonParaRxdb,
  normalizarEventoJson
};
