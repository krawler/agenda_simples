const lembretesSchema = {
  title: 'lembretes',
  version: 0,
  type: 'object',
  properties: {
    id: { type: 'string', primary: true },
    eventoId: { type: 'string' },
    ocorrenciaId: { type: 'string' },
    tipo: { type: 'string' },
    canal: { type: 'string' },
    enviado: { type: 'boolean', default: false },
    enviadoEm: { type: 'string', format: 'date-time' },
    userId: { type: 'string' },
    createdAt: { type: 'string', format: 'date-time' },
    updatedAt: { type: 'string', format: 'date-time' }
  },
  required: ['id', 'eventoId', 'tipo', 'createdAt', 'updatedAt']
};

module.exports = { lembretesSchema };
