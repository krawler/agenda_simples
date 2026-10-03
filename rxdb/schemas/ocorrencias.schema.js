export const ocorrenciasSchema = {
  title: 'ocorrencias',
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: { type: 'string', maxLength: 64 },
    eventoId: { type: 'string', maxLength: 64 },
    inicio: { type: 'string', format: 'date-time', maxLength: 32 },
    fim: { type: 'string', format: 'date-time', maxLength: 32 },
    status: { type: 'string', maxLength: 32, default: 'pendente' },
    skip: { type: 'boolean', default: false },
    userId: { type: 'string', maxLength: 64 },
    createdAt: { type: 'string', format: 'date-time', maxLength: 32 },
    updatedAt: { type: 'string', format: 'date-time', maxLength: 32 }
  },
  required: ['id', 'eventoId', 'inicio', 'fim', 'createdAt', 'updatedAt'],
  indexes: ['eventoId', 'inicio', 'status']
};
