// alerta.js - Funções de alerta e contadores de tempo
// Carregar antes de jquery-script.js

// Variáveis globais compartilhadas (inicialização defensiva)
window.__agendaAlertAudioContext = window.__agendaAlertAudioContext || null;
window.__halfTimeTimers = window.__halfTimeTimers || {};

/**
 * Emite um som de alerta usando Web Audio API
 */
function emitirSomAlerta() {
  try {
    if (!('AudioContext' in window || 'webkitAudioContext' in window)) {
      return;
    }

    var AudioCtor = window.AudioContext || window.webkitAudioContext;
    var context = window.__agendaAlertAudioContext || new AudioCtor();
    if (!context) {
      return;
    }

    if (context.state === 'suspended') {
      context.resume();
    }

    var oscillator = context.createOscillator();
    var gain = context.createGain();
    oscillator.type = 'triangle';
    oscillator.frequency.value = 880;
    gain.gain.value = 0.0001;

    oscillator.connect(gain);
    gain.connect(context.destination);

    var now = context.currentTime;
    gain.gain.exponentialRampToValueAtTime(0.12, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.25);

    oscillator.start(now);
    oscillator.stop(now + 0.25);

    window.__agendaAlertAudioContext = context;
  } catch (e) {
    // Silencia falhas de áudio sem quebrar a UI.
  }
}

/**
 * Atualiza o banner de alertas se houver eventos nos próximos 30/15 minutos
 */
function atualizarBannerAlertasSeNecessario(data) {
  if (!data || !data.eventos || !data.eventos.length) {
    return;
  }

  var deveExibir = data.eventos.some(function(evento) {
    return evento.minutos_restantes === 30 || evento.minutos_restantes === 15;
  });

  if (!deveExibir) {
    return;
  }

  var banner = document.getElementById('alerts-banner');
  if (banner && banner.style.display === 'none') {
    banner.style.display = '';
  }

  var container = document.getElementById('alerts-container');
  if (!container) {
    return;
  }

  fetch('/alerts')
    .then(function(response) {
      if (!response.ok) {
        throw new Error('Falha ao recarregar alertas');
      }
      return response.text();
    })
    .then(function(html) {
      container.innerHTML = html;
    })
    .catch(function() {
      // Silencia falha de render sem quebrar a UI.
    });
}

/**
 * Verifica se notificações de meio de evento estão habilitadas
 */
function halfTimeNotificationsEnabled() {
  try {
    return localStorage.getItem('notificacaoMeioEvento') === 'true';
  } catch (e) {
    return false;
  }
}

/**
 * Limpa todos os timers de alerta de meio de evento agendados
 */
function clearHalfTimeAlerts() {
  Object.keys(window.__halfTimeTimers || {}).forEach(function(id) {
    var timer = window.__halfTimeTimers[id];
    if (timer) {
      clearTimeout(timer);
    }
    delete window.__halfTimeTimers[id];
  });
}


/**
 * Fecha o elemento alvo do botão de fechar
 */
function closeTargetByButton(button) {
  var targetId = button.getAttribute && button.getAttribute('data-close-target');
  var target = targetId ? document.getElementById(targetId) : null;

  if (target) {
    if (target.tagName === 'DIALOG' && typeof target.close === 'function') {
      target.close();
      return;
    }
    target.style.display = 'none';
    return;
  }

  var closestAlert = button.closest('.alert');
  if (closestAlert) {
    closestAlert.style.display = 'none';
    return;
  }

  var closestList = button.closest('[id^="google-events-list-"]');
  if (closestList) {
    closestList.style.display = 'none';
    return;
  }

  if (button.parentElement) {
    button.parentElement.style.display = 'none';
  }
}

