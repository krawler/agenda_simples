function normalizarRecorrencia(evento) {
  const recorrencia = evento?.recorrencia ?? {};

  return {
    tipo: evento?.repeat ?? recorrencia.tipo ?? 'none',
    until: evento?.until ?? recorrencia.until ?? null,
    diasSemana: Array.isArray(recorrencia.diasSemana)
      ? recorrencia.diasSemana
      : []
  };
}

function eventoEhRecorrente(evento) {
  const tipo = normalizarRecorrencia(evento).tipo;
  return Boolean(tipo && tipo !== 'none');
}

module.exports = {
  normalizarRecorrencia,
  eventoEhRecorrente
};
