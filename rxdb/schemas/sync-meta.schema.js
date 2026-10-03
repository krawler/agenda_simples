export const syncMetaSchema = {
  title: 'sync_meta',
  version: 0,
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: { type: 'string', maxLength: 64 },
    lastSyncAt: { type: 'string', format: 'date-time', maxLength: 32 },
    deviceId: { type: 'string', maxLength: 64 },
    lastSequence: { type: 'number', minimum: 0 },
    status: { type: 'string', maxLength: 32, default: 'ok' },
    updatedAt: { type: 'string', format: 'date-time', maxLength: 32 }
  },
  required: ['id', 'updatedAt']
};
