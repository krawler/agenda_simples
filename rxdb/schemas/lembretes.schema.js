export const lembretesSchema = {
  title: 'lembretes',
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: { type: 'string', maxLength: 64 },
    eventoId: { type: 'string', maxLength: 64 },
    ocorrenciaId: { type: 'string', maxLength: 64 },
    tipo: { type: 'string', maxLength: 32 },
    canal: { type: 'string', maxLength: 32 },
    enviado: { type: 'boolean', default: false },
    enviadoEm: { type: 'string', format: 'date-time', maxLength: 32 },
    userId: { type: 'string', maxLength: 64 },
    createdAt: { type: 'string', format: 'date-time', maxLength: 32 },
    updatedAt: { type: 'string', format: 'date-time', maxLength: 32 }
  },
  required: ['id', 'eventoId', 'tipo', 'createdAt', 'updatedAt'],
  indexes: ['eventoId', 'ocorrenciaId', 'enviado']
};
