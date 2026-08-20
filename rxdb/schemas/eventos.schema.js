const eventosSchema = {
  title: 'eventos',
  version: 0,
  type: 'object',
  properties: {
    id: { type: 'string', primary: true },
    titulo: { type: 'string' },
    inicio: { type: 'string', format: 'date-time' },
    duracaoMinutos: { type: 'number', minimum: 0 },
    descricao: { type: 'string' },
    except: {
      type: 'array',
      items: { type: 'string' }
    },
    recorrencia: {
      type: 'object',
      properties: {
        tipo: { type: 'string' },
        until: { type: 'string' },
        diasSemana: {
          type: 'array',
          items: { type: 'number', minimum: 0, maximum: 6 }
        }
      },
      required: ['tipo']
    },
    status: { type: 'string', default: 'ativo' },
    cancelado: { type: 'boolean', default: false },
    concluido: { type: 'boolean', default: false },
    userId: { type: 'string' },
    deleted: { type: 'boolean', default: false },
    createdAt: { type: 'string', format: 'date-time' },
    updatedAt: { type: 'string', format: 'date-time' }
  },
  required: ['id', 'titulo', 'inicio', 'createdAt', 'updatedAt']
};

module.exports = { eventosSchema };
