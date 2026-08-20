const { eventosSchema } = require('./eventos.schema');
const { ocorrenciasSchema } = require('./ocorrencias.schema');
const { lembretesSchema } = require('./lembretes.schema');
const { syncMetaSchema } = require('./sync-meta.schema');

const rxdbSchemas = {
  eventos: eventosSchema,
  ocorrencias: ocorrenciasSchema,
  lembretes: lembretesSchema,
  syncMeta: syncMetaSchema
};

module.exports = { rxdbSchemas };
