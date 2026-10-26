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
 * Agenda alertas para o meio dos eventos baseados em atributos data-* do DOM
 */
function scheduleHalfTimeAlerts(root) {
  try {
    if (!halfTimeNotificationsEnabled()) {
      clearHalfTimeAlerts();
      return;
    }

    var container = root || document;
    var items = container.querySelectorAll('[data-occ-iso][data-dur-min]');
    var now = Date.now();
    items.forEach(function(node) {
      var occIso = node.getAttribute('data-occ-iso');
      var durMin = Number(node.getAttribute('data-dur-min') || 0);
      if (!occIso || !durMin) return;
      var start = Date.parse(occIso);
      if (isNaN(start)) return;
      var halfMs = start + (durMin * 60000 / 2);
      var id = node.getAttribute('data-occ-iso') + '|' + durMin;
      // Se o meio já passou, pula
      if (halfMs <= now) {
        return;
      }
      // Se timer já agendado, pula
      if (window.__halfTimeTimers[id]) return;
      var delay = Math.max(0, halfMs - now);
      var t = setTimeout(function() {
        // Dispara notificação
        try {
          if (Notification.permission === 'granted' && halfTimeNotificationsEnabled()) {
            var titulo = node.querySelector('.font-medium a') ? node.querySelector('.font-medium a').textContent.trim() : 'Evento';
            dispararNotificacao('⏱️ ' + titulo, 'Evento ' + titulo + ' alcançou a metade do tempo', '/favicon.ico');
          }
          // Speech synthesis
          try {
            if (window.speechSynthesis && halfTimeNotificationsEnabled()) {
              var utter = new SpeechSynthesisUtterance('Evento ' + (node.textContent || 'evento') + ' alcançou a metade do tempo');
              utter.volume = 0.5;
              speechSynthesis.speak(utter);
            }
          } catch (e) {}
        } finally {
          delete window.__halfTimeTimers[id];
        }
      }, delay);
      window.__halfTimeTimers[id] = t;
    });
  } catch (e) {
    // ignore
  }
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

/**
 * Atualiza contadores regressivos de alerta
 */
function updateAlertCountdowns() {
  var now = Date.now();

  $('.js-alert-countdown').each(function() {
    var occIso = this.getAttribute('data-occ-iso');
    if (!occIso) {
      return;
    }

    var targetTime = new Date(occIso).getTime();
    var remainingSeconds = Math.max(0, Math.ceil((targetTime - now) / 1000));

    var hourEl = this.querySelector('.js-cd-h');
    var minuteEl = this.querySelector('.js-cd-m');
    var secondEl = this.querySelector('.js-cd-s');

    if (remainingSeconds <= 0) {
      if (hourEl) {
        hourEl.textContent = 'Agora';
        hourEl.setAttribute('aria-label', 'Agora');
        hourEl.style.setProperty('--value', '0');
      }
      if (minuteEl) {
        minuteEl.textContent = '';
        minuteEl.setAttribute('aria-label', '');
        minuteEl.style.setProperty('--value', '0');
      }
      if (secondEl) {
        secondEl.textContent = '';
        secondEl.setAttribute('aria-label', '');
        secondEl.style.setProperty('--value', '0');
      }
      this.parentElement.parentElement.parentElement.style.display = 'none';
      return;
    }

    var hours = Math.floor(remainingSeconds / 3600);
    var minutes = Math.floor((remainingSeconds % 3600) / 60);
    var seconds = remainingSeconds % 60;

    if (hourEl) {
      hourEl.textContent = String(hours).padStart(2, '0');
      hourEl.setAttribute('aria-label', String(hours));
      hourEl.style.setProperty('--value', String(hours));
    }
    if (minuteEl) {
      minuteEl.textContent = String(minutes).padStart(2, '0');
      minuteEl.setAttribute('aria-label', String(minutes));
      minuteEl.style.setProperty('--value', String(minutes));
    }
    if (secondEl) {
      secondEl.textContent = String(seconds).padStart(2, '0');
      secondEl.setAttribute('aria-label', String(seconds));
      secondEl.style.setProperty('--value', String(seconds));
    }
  });
}

/**
 * Atualiza barras de progresso dos eventos
 */
function updateEventProgress() {
  var now = Date.now();
  $('.js-event-progress').each(function() {
    var occIso = this.getAttribute('data-occ-iso');
    var durMin = Number(this.getAttribute('data-dur-min') || 0);
    if (!occIso || !durMin) {
      return;
    }

    var startTime = new Date(occIso).getTime();
    if (isNaN(startTime)) {
      return;
    }

    var durationMs = durMin * 60 * 1000;
    var elapsedMs = Math.max(0, now - startTime);
    var progress = Math.max(0, Math.min(100, Math.round((elapsedMs / durationMs) * 100)));

    this.style.setProperty('--value', String(progress));
    this.setAttribute('aria-valuenow', String(progress));
    this.textContent = progress + '%';
  });
}

/**
 * Inicializa contadores de alerta e progresso
 */
function initAlertCountdowns() {
  updateAlertCountdowns();
  updateEventProgress();
  if (window.__agendaAlertCountdownInterval) {
    return;
  }
  window.__agendaAlertCountdownInterval = setInterval(function() {
    updateAlertCountdowns();
    updateEventProgress();
  }, 1000);
}
