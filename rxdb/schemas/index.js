import { eventosSchema } from './eventos.schema.js';
import { ocorrenciasSchema } from './ocorrencias.schema.js';
import { lembretesSchema } from './lembretes.schema.js';
import { syncMetaSchema } from './sync-meta.schema.js';

export const rxdbSchemas = {
  eventos: eventosSchema,
  ocorrencias: ocorrenciasSchema,
  lembretes: lembretesSchema,
  syncMeta: syncMetaSchema
};
