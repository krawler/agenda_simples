const ocorrenciasSchema = {
  title: 'ocorrencias',
  version: 0,
  type: 'object',
  properties: {
    id: { type: 'string', primary: true },
    eventoId: { type: 'string' },
    inicio: { type: 'string', format: 'date-time' },
    fim: { type: 'string', format: 'date-time' },
    status: { type: 'string', default: 'pendente' },
    skip: { type: 'boolean', default: false },
    userId: { type: 'string' },
    createdAt: { type: 'string', format: 'date-time' },
    updatedAt: { type: 'string', format: 'date-time' }
  },
  required: ['id', 'eventoId', 'inicio', 'fim', 'createdAt', 'updatedAt']
};

module.exports = { ocorrenciasSchema };
