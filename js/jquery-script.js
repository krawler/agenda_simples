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
        var interruptLinkHtml = ' <a href="#" class="link link-hover text-xs ml-2" onclick="interruptSync(); return false;">Interromper</a>';
        var html = '<div class="flex items-start justify-between gap-2">'
                  + '<div class="flex flex-col min-w-0 flex-1">'
                  + '  <span class="text-lg font-semibold">Sincronizando com Google Calendar...</span>'
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

  function interruptSync() {
    $.post('/interrupt-sync', function() {
      if (eventSource) {
        eventSource.close();
      }
      $("#sync-google").prop('disabled', false);
      $("#sync-google").removeClass('skeleton');
      var detailsLinkHtml = (window.syncLogsData && window.syncLogsData.length) ? ' <a href="#" class="link link-hover text-xs ml-2" onclick="openSyncDetailsModal(); return false;">Exibir</a>' : '';
      $("#sync-status-detail").html('Sincronização interrompido' + detailsLinkHtml);
    });
  }

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

  $("#sync-google").on("click", function(event) {
    event.preventDefault();
    startSyncStream();
  });
});
