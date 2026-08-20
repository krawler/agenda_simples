const syncMetaSchema = {
  title: 'sync_meta',
  version: 0,
  type: 'object',
  properties: {
    id: { type: 'string', primary: true },
    lastSyncAt: { type: 'string', format: 'date-time' },
    deviceId: { type: 'string' },
    lastSequence: { type: 'number', minimum: 0 },
    status: { type: 'string', default: 'ok' },
    updatedAt: { type: 'string', format: 'date-time' }
  },
  required: ['id', 'updatedAt']
};

module.exports = { syncMetaSchema };
