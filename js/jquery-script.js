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

      data.eventos.forEach(function(evento) {
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

function verificarEventosMetadeTempo() {
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

  fetch('/api/eventos-metade-tempo')
    .then(function(response) {
      return response.json();
    })
    .then(function(data) {
      if (!data || !data.eventos || !data.eventos.length) {
        return;
      }

      data.eventos.forEach(function(evento) {
        dispararNotificacao(
          '⏱️ ' + evento.titulo,
          'Já se passaram ' + evento.minutos_passados + ' minutos de ' + evento.duracao_minutos + ' minutos',
          '/favicon.ico'
        );
        // Emitir beep
        try {
          if (window.speechSynthesis) {
            var utterance = new SpeechSynthesisUtterance('Alerta: ' + evento.titulo + ', já se passaram ' + evento.minutos_passados + ' minutos');
            utterance.volume = 0.5;
            speechSynthesis.speak(utterance);
          }
        } catch (e) {
          // Silencia falhas
        }
      });
    })
    .catch(function() {
      // Silencia falhas de consulta sem quebrar a UI.
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

  function initAlertCountdowns() {
    updateAlertCountdowns();
    if (window.__agendaAlertCountdownInterval) {
      return;
    }
    window.__agendaAlertCountdownInterval = setInterval(updateAlertCountdowns, 1000);
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
  verificarEventosMetadeTempo();
  window.__agendaNotificationInterval = setInterval(verificarEventosProximos, 60000);
  window.__agendaMetadeTempoInterval = setInterval(verificarEventosMetadeTempo, 60000);

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
