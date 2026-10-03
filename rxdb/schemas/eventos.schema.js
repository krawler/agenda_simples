export const eventosSchema = {
  title: 'eventos',
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: { type: 'string', maxLength: 64 },
    titulo: { type: 'string', minLength: 1 },
    inicio: { type: 'string', format: 'date-time', maxLength: 32 },
    duracaoMinutos: { type: 'number', minimum: 0, default: 0 },
    descricao: { type: 'string', default: '' },
    except: {
      type: 'array',
      items: { type: 'string' },
      default: []
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
    status: { type: 'string', maxLength: 32, default: 'ativo' },
    cancelado: { type: 'boolean', default: false },
    concluido: { type: 'boolean', default: false },
    userId: { type: 'string', maxLength: 64, default: 'local-user' },
    removido: { type: 'boolean', default: false },
    createdAt: { type: 'string', format: 'date-time', maxLength: 32 },
    updatedAt: { type: 'string', format: 'date-time', maxLength: 32 }
  },
  required: ['id', 'titulo', 'inicio', 'userId', 'createdAt', 'updatedAt'],
  indexes: ['inicio', 'status', 'updatedAt', 'userId'],
  additionalProperties: false
};
