function montarMensagemLembrete(evento, ocorrencia) {
  const inicio = ocorrencia?.inicio ?? evento?.inicio ?? new Date().toISOString();
  const titulo = evento?.titulo ?? 'Evento';
  const descricao = evento?.descricao ?? evento?.desc ?? '';

  return [
    'Lembrete: seu evento começa em breve.',
    '',
    `• Evento: ${titulo}`,
    `• Quando: ${inicio}`,
    descricao ? `• Descrição: ${descricao}` : '',
    '',
    '— Agenda Simples'
  ].filter(Boolean).join('\n');
}

function precisaEnviarLembrete(evento, ocorrencia) {
  return Boolean(evento && ocorrencia && ocorrencia.inicio);
}

module.exports = {
  montarMensagemLembrete,
  precisaEnviarLembrete
};
