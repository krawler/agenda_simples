function abrirConfig() {
  var modal = document.getElementById('config-modal');
  if (!modal) {
    return;
  }
  if (typeof modal.showModal === 'function') {
    modal.showModal();
    return;
  }
  modal.setAttribute('open', 'open');
}

function abrirIdeiasPlanos() {
  var panel = document.getElementById('ideas-plans-panel');
  if (panel) {
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }

  var fallback = document.querySelector('[data-ideas-plans]');
  if (fallback) {
    fallback.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

function contextoSeguroParaNotificacao() {
  if (window.isSecureContext) {
    return true;
  }

  var host = window.location && window.location.hostname ? window.location.hostname : '';
  return host === 'localhost' || host === '127.0.0.1' || host === '::1';
}

function initNotificacoes() {
  if (!('Notification' in window)) {
    localStorage.setItem('notificacoesNavegador', 'false');
    return;
  }

  if (!contextoSeguroParaNotificacao()) {
    localStorage.setItem('notificacoesNavegador', 'false');
    return;
  }

  if (Notification.permission === 'granted') {
    localStorage.setItem('notificacoesNavegador', 'true');
  } else if (Notification.permission === 'denied') {
    localStorage.setItem('notificacoesNavegador', 'false');
  }
}

window.solicitarPermissaoNotificacao = function solicitarPermissaoNotificacao() {
  if (!('Notification' in window)) {
    return Promise.resolve({
      ok: false,
      permission: 'unsupported',
      message: 'Este navegador não suporta notificações.'
    });
  }

  if (!contextoSeguroParaNotificacao()) {
    return Promise.resolve({
      ok: false,
      permission: Notification.permission,
      message: 'Abra em localhost/127.0.0.1 (ou HTTPS) para habilitar notificações.'
    });
  }

  return Notification.requestPermission().then(function(permission) {
    if (permission === 'granted') {
      localStorage.setItem('notificacoesNavegador', 'true');
      return {
        ok: true,
        permission: permission,
        message: 'Permissão concedida.'
      };
    }

    localStorage.setItem('notificacoesNavegador', 'false');
    return {
      ok: false,
      permission: permission,
      message: permission === 'denied'
        ? 'Permissão negada. Libere nas configurações do site do navegador.'
        : 'Permissão não concedida.'
    };
  }).catch(function(err) {
    return {
      ok: false,
      permission: Notification.permission,
      message: 'Erro ao solicitar permissão: ' + (err && err.message ? err.message : err)
    };
  });
};

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

window.__agendaEventosAvisados = window.__agendaEventosAvisados || {};

function dispararNotificacao(titulo, mensagem, icone) {
  if (Notification.permission !== 'granted') {
    return;
  }

  var notificacao = new Notification(titulo, {
    body: mensagem,
    icon: icone || '/favicon.ico',
    requireInteraction: true,
    tag: 'agenda-notificacao'
  });

  emitirSomAlerta();

  notificacao.onclick = function() {
    window.focus();
    this.close();
  };

  setTimeout(function() {
    if (notificacao && notificacao.close) {
      notificacao.close();
    }
  }, 10000);
}

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

function verificarEventosProximos() {
  if (!('Notification' in window)) {
    return;
  }

  if (Notification.permission !== 'granted') {
    return;
  }

  var notificacoesHabilitadas = localStorage.getItem('notificacoesNavegador') === 'true';
  if (!notificacoesHabilitadas) {
    return;
  }

  var alertasMinutos = JSON.parse(localStorage.getItem('alertasMinutos') || '[60,30,15]');
  alertasMinutos = (alertasMinutos || []).map(function(value) {
    return parseInt(value, 10);
  }).filter(function(value) {
    return Number.isInteger(value) && value > 0;
  });

  if (!alertasMinutos.length) {
    return;
  }

  fetch('/api/eventos-proximos', {
    headers: {
      'X-Alertas-Minutos': JSON.stringify(alertasMinutos)
    }
  })
    .then(function(response) {
      return response.json();
    })
    .then(function(data) {
      if (!data || !data.eventos || !data.eventos.length) {
        return;
      }

      atualizarBannerAlertasSeNecessario(data);

      data.eventos.forEach(function(evento) {
        var chave = [evento.id, evento.minutos_restantes, evento.hora].join('|');
        if (window.__agendaEventosAvisados[chave]) {
          return;
        }

        window.__agendaEventosAvisados[chave] = true;
        dispararNotificacao(
          '⏰ ' + evento.titulo,
          'Evento em ' + evento.minutos_restantes + ' minutos (' + evento.hora + ')',
          '/favicon.ico'
        );
      });
    })
    .catch(function() {
      // Silencia falhas de consulta sem quebrar a UI.
    });
}


// Schedule per-event half-time alerts using DOM data attributes.
window.__halfTimeTimers = window.__halfTimeTimers || {};

function halfTimeNotificationsEnabled() {
  try {
    return localStorage.getItem('notificacaoMeioEvento') === 'true';
  } catch (e) {
    return false;
  }
}

function clearHalfTimeAlerts() {
  Object.keys(window.__halfTimeTimers || {}).forEach(function(id) {
    var timer = window.__halfTimeTimers[id];
    if (timer) {
      clearTimeout(timer);
    }
    delete window.__halfTimeTimers[id];
  });
}

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
      // If half already passed, skip
      if (halfMs <= now) {
        return;
      }
      // If timer already scheduled, skip
      if (window.__halfTimeTimers[id]) return;
      var delay = Math.max(0, halfMs - now);
      var t = setTimeout(function() {
        // Fire notification
        try {
          if (Notification.permission === 'granted' && halfTimeNotificationsEnabled()) {
            var titulo = node.querySelector('.font-medium a') ? node.querySelector('.font-medium a').textContent.trim() : 'Evento';
            dispararNotificacao('⏱️ ' + titulo, 'Evento ' + titulo + ' alcançou a metade do tempo', '/favicon.ico');
          }
          // speech
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

// Run on initial load
document.addEventListener('DOMContentLoaded', function() {
  scheduleHalfTimeAlerts(document);
  // Inicializa contadores de alerta se existirem (usa a classe correta)
});

// Re-schedule after HTMX swaps (day panel updates)
if (window.htmx && htmx.on) {
  htmx.on('afterSwap', function(evt) {
    updateAlertCountdowns();
    scheduleHalfTimeAlerts(document);
  });
}

$(document).ready(function() {
  var $syncStatus = $("#sync-status");
  var eventSource;

  function startSyncStream() {
    if (eventSource) {
      eventSource.close();
    }

    eventSource = new EventSource('/sync-stream');
    $("#sync-google").prop('disabled', true);
    $("#sync-google").addClass('skeleton');
    $(".loading-infinity").show();

    eventSource.onmessage = function(event) {
      try {
        var data = JSON.parse(event.data);
      } catch (err) {
        return;
      }

      if (data.status) {
        if ($syncStatus.length === 0) {
          $("#sync-container").html('<div id="sync-status"></div>');
          $syncStatus = $("#sync-status");
        }
        var alertClass = data.status.toLowerCase().includes('sucesso') || data.status.toLowerCase().includes('conclu')
          ? 'alert alert-success shadow-sm'
          : data.status.toLowerCase().includes('erro')
            ? 'alert alert-error shadow-sm'
            : 'alert alert-info shadow-sm';

        var detailsLinkHtml = (data.logs && data.logs.length) ? ' <a href="#" class="link link-hover text-xs ml-2" onclick="openSyncDetailsModal(); return false;">Exibir</a>' : '';
        var interruptLinkHtml = ' <a href="#" class="link link-hover text-xs ml-2" onclick="window.interruptSync(); return false;">Interromper</a>';
        var html = '<div class="flex flex-wrap contents gap-2">'
                  + ' <span class="loading loading-infinity loading-sm"></span>' 
                  + '  <span class="text-lg font-semibold">Sincronizando com Google Calendar:</span>'
                  + '<div class="space-y-1 max-h-60 overflow-y-auto">'
                  
                  + '  <span id="sync-status-detail" class="text-sm opacity-70">' + data.status + detailsLinkHtml + interruptLinkHtml + '</span>'
                  + '</div>'
                  + '<button type="button" class="btn btn-xs btn-ghost btn-circle close-btn flex-shrink-0" data-close-target="sync-status" title="Fechar">✕</button>'
                  + '</div>';

        $syncStatus.attr('class', alertClass).html(html).slideDown(200);
      }

      if (data.completed) {
        // Armazena logs para o modal
        if (data.logs) {
          window.syncLogsData = data.logs;
        }
        
        if (data.importados || data.exportados) {
          var listsHtml = '';
          if (data.importados && data.importados.length) {
            listsHtml += renderSyncEventList(data.importados, 'importados');
          }
          if (data.exportados && data.exportados.length) {
            listsHtml += renderSyncEventList(data.exportados, 'exportados');
          }
          if (listsHtml) {
            $("#sync-container").append(listsHtml);
          }
        }
        eventSource.close();
        $("#sync-google").prop('disabled', false);
        $("#sync-google").removeClass('skeleton');
        $(".loading-infinity").hide();
      }
    };

    eventSource.onerror = function() {
      if (eventSource.readyState === EventSource.CLOSED) {
        $("#sync-google").prop('disabled', false);
      } else {
        $("#sync-status-detail").text('Erro de conexão com o servidor.');
      }
    };
  }

  window.interruptSync = function() {
    $.post('/interrupt-sync', function() {
      if (eventSource) {
        eventSource.close();
      }
      $("#sync-google").prop('disabled', false);
      $("#sync-google").removeClass('skeleton');
      $(".loading-infinity").hide();
      var detailsLinkHtml = (window.syncLogsData && window.syncLogsData.length) ? ' <a href="#" class="link link-hover text-xs ml-2" onclick="openSyncDetailsModal(); return false;">Exibir</a>' : '';
      $("#sync-status-detail").html('Sincronização interrompido' + detailsLinkHtml);
    });
  };

  function formatDateTimeForDisplay(dateTime) {
    if (!dateTime) return '';
    var normalized = String(dateTime).replace(' ', 'T');
    if (normalized.endsWith('Z')) {
      normalized = normalized.replace(/Z$/, '+00:00');
    }
    var date = new Date(normalized);
    if (isNaN(date.getTime())) {
      return String(dateTime);
    }
    var day = String(date.getDate()).padStart(2, '0');
    var month = String(date.getMonth() + 1).padStart(2, '0');
    var year = date.getFullYear();
    var hours = String(date.getHours()).padStart(2, '0');
    var minutes = String(date.getMinutes()).padStart(2, '0');
    return day + '/' + month + '/' + year + ' às ' + hours + ':' + minutes;
  }

  function renderSyncEventList(events, mode) {
    var modeLabel = mode === 'importados' ? 'Eventos Importados do Google' : 'Eventos Exportados para o Google';
    var listClass = mode === 'importados' ? 'alert alert-info shadow-sm mt-4' : 'alert alert-success shadow-sm mt-4';
    var items = events.map(function(ev) {
      var title = ev.titulo || ev.summary || 'Sem título';
      var start = formatDateTimeForDisplay(ev.inicio || ev.start || '');
      var description = ev.desc || ev.description || '';
      var detalhes = [];
      if (ev.repeat) {
        detalhes.push(ev.repeat);
      }
      if (ev.until) {
        detalhes.push('até ' + ev.until);
      }
      var metaHtml = detalhes.length
        ? '<div class="flex flex-wrap gap-2 text-xs opacity-60 mt-1">' +
            detalhes.map(function(d) { return '<span class="badge badge-outline badge-sm">' + $('<div>').text(d).html() + '</span>'; }).join('') +
          '</div>'
        : '';
      var descriptionHtml = description
        ? '<div class="text-sm opacity-70">' + $('<div>').text(description).html() + '</div>'
        : '';

      return '<div class="rounded-xl border border-base-300 bg-base-200 p-4 space-y-2">'
        + '<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">'
        + '<span class="font-semibold">' + $('<div>').text(title).html() + '</span>'
        + '<span class="text-xs opacity-70">' + $('<div>').text(start).html() + '</span>'
        + '</div>'
        + descriptionHtml
        + metaHtml
        + '</div>';
    }).join('');
    return '<div id="google-events-list-' + mode + '" class="' + listClass + '">' 
      + '<div class="flex items-center justify-between mb-3">'
      + '<span class="font-semibold">' + modeLabel + '</span>'
      + '<button type="button" class="btn btn-xs btn-ghost btn-circle close-btn" data-close-target="google-events-list-' + mode + '" title="Fechar">✕</button>'
      + '</div>'
      + '<div class="space-y-3 max-h-80 overflow-y-auto">' + items + '</div>'
      + '</div>';
  }

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

  function updateAlertCountdowns() {
    console.log('[agenda] updateAlertCountdowns: called');
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

      // debug: report that we updated this countdown
      try {
        if (this && this.getAttribute) {
          // only log once per element per run to avoid noisy output
          if (!this.__loggedCountdown) {
            console.log('[agenda] updateAlertCountdowns: updating countdown for', this.getAttribute('data-occ-iso'));
            this.__loggedCountdown = true;
          }
        }
      } catch (e) {}

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

  function initAlertCountdowns() {
    console.log('[agenda] initAlertCountdowns: called');
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

  document.addEventListener('click', function(event) {
    var button = event.target && event.target.closest && event.target.closest('.close-btn');
    if (!button) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    closeTargetByButton(button);
  });

  document.addEventListener('htmx:afterSwap', initAlertCountdowns);
  initAlertCountdowns();
  initNotificacoes();
  verificarEventosProximos();
  window.__agendaNotificationInterval = setInterval(verificarEventosProximos, 60000);
  $("#sync-google").on("click", function(event) {
    event.preventDefault();
    startSyncStream();
  });

  // Enter como Tab no formulário de inserção e edição
  $(document).on('keydown', '.form-control, input, select, textarea', function(event) {
    if (event.key === 'Enter' && !event.shiftKey && !event.ctrlKey) {
      event.preventDefault();
      var $this = $(this);
      var $form = $this.closest('form');
      if (!$form.length) {
        return;
      }
      var $inputs = $form.find('input, select, textarea').not(':disabled');
      var index = $inputs.index(this);
      if (index >= 0 && index < $inputs.length - 1) {
        $inputs.eq(index + 1).focus();
      } else {
        $form.find('button[type="submit"]').focus();
      }
    }
  });

  // Carrega e exibe os próximos eventos ao clicar no botão
  $(document).on('click', '#proximos-eventos-btn', function(event) {
    event.preventDefault();
    var $proximosContainer = $('#proximos-eventos');
    if ($proximosContainer.length === 0) {
      // Fetch and render the proximos eventos
      $.get('/alerts', function(data) {
        $('#alerts-container').html(data);
        // Scroll to the proximos eventos section
        $('#proximos-eventos').get(0).scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    } else {
      $proximosContainer.get(0).scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});
