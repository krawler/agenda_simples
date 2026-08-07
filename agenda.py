#!/usr/bin/env python3
"""Agenda de eventos simples via linha de comando.

Comandos:
  new    cria um evento (com recorrencia opcional)
  edit   edita campos de um evento existente
  list   lista eventos (dia atual, data informada, ou proximas N horas)
  alerts mostra eventos que iniciam nos proximos 60 minutos
  watch  monitora e avisa (com beep) eventos que iniciam em 60, 30 e 15 minutos
  rm     remove um evento pelo id
  sync   sincroniza eventos com Google Calendar

Exemplos:
  python agenda.py new "Reuniao" --at "2026-07-01 15:00" --dur 60 --desc "com o time"
  python agenda.py new "Standup" --at "09:00" --repeat weekdays
  python agenda.py new "Pagamento" --at "2026-07-05 10:00" --repeat monthly --until 2026-12-31
  python agenda.py edit 3 --at "16:00" --desc "remarcada"
  python agenda.py list
  python agenda.py list --date 2026-07-05
  python agenda.py list --hours 6
  python agenda.py alerts
  python agenda.py watch
  python agenda.py rm 3
  python agenda.py sync
"""
import argparse
import calendar
import json
import sys
import os
from datetime import datetime, date, time, timedelta
from pathlib import Path

# Garante saida UTF-8 mesmo em consoles Windows (cp1252).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DB = Path(__file__).with_name("eventos.json")
FMT = "%Y-%m-%d %H:%M"
DATA_FMT = "%Y-%m-%d"
ALERTAS_MIN = [60, 30, 15]  # 1h, 30min, 15min antes
ALERTA_MIN = 60  # Minutos de antecedência para notificações (usado pelo notificador)
REPEATS = ("none", "daily", "weekdays", "weekly", "monthly")

# Google Calendar integration
GOOGLE_CREDENTIALS_FILE = Path(__file__).with_name("credentials.json")
GOOGLE_TOKEN_FILE = Path(__file__).with_name("token.json")
GOOGLE_CALENDAR_ID = "primary"  # Use 'primary' for the main calendar

# Try to import Google Calendar libraries
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from google.auth.exceptions import RefreshError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    RefreshError = Exception  # Fallback para type hints

SCOPES = ['https://www.googleapis.com/auth/calendar']


# ---------------------------------------------------------------- persistencia
def carregar():
    if DB.exists():
        return json.loads(DB.read_text(encoding="utf-8"))
    return []


def salvar(eventos):
    DB.write_text(json.dumps(eventos, ensure_ascii=False, indent=2), encoding="utf-8")


def proximo_id(eventos):
    return max((e["id"] for e in eventos), default=0) + 1


# --------------------------------------------------------------------- helpers
def parse_dt(texto):
    """Aceita 'YYYY-MM-DD HH:MM' ou apenas 'HH:MM' (assume hoje)."""
    texto = texto.strip()
    try:
        return datetime.strptime(texto, FMT)
    except ValueError:
        pass
    try:
        hora = datetime.strptime(texto, "%H:%M").time()
        return datetime.combine(datetime.now().date(), hora)
    except ValueError:
        sys.exit(f"Data/hora invalida: {texto!r}. Use 'YYYY-MM-DD HH:MM' ou 'HH:MM'.")


def parse_data(texto):
    try:
        return datetime.strptime(texto.strip(), DATA_FMT).date()
    except ValueError:
        sys.exit(f"Data invalida: {texto!r}. Use 'YYYY-MM-DD'.")


def evento_inicio(e):
    return datetime.strptime(e["inicio"], FMT)


def beep():
    """Emite um beep audivel (winsound no Windows, BEL nos demais)."""
    try:
        if sys.platform == "win32":
            import winsound
            winsound.Beep(880, 400)  # 880 Hz por 400 ms
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
    except Exception:
        pass


def validar_until(until_str, inicio_dt):
    """Valida se a data 'until' não é anterior à data de início do evento."""
    if until_str:
        until_date = parse_data(until_str)
        if until_date < inicio_dt.date():
            sys.exit(f"Erro: a data --until ({until_date}) não pode ser anterior à data de início ({inicio_dt.date()}).")


def _ultimo_dia_mes(ano, mes):
    """Retorna o último dia do mês (1-31)."""
    return calendar.monthrange(ano, mes)[1]


def _dia_efetivo_mensal(base_date, target_date):
    """
    Retorna o dia efetivo do mês para recorrência monthly.
    Regra: se o dia base não existe no mês alvo, usa o último dia do mês.
    """
    base_day = base_date.day
    target_year = target_date.year
    target_month = target_date.month
    ultimo_dia = _ultimo_dia_mes(target_year, target_month)
    return base_day if base_day <= ultimo_dia else ultimo_dia


# ------------------------------------------------------------------ recorrencia
def ocorre_no_dia(e, dia):
    """Diz se o evento (single ou recorrente) acontece em `dia` (date)."""
    base = evento_inicio(e).date()
    if dia < base:
        return False
    if e.get("until") and dia > parse_data(e["until"]):
        return False
    if dia.isoformat() in (e.get("except") or []):
        return False  # ocorrencia removida individualmente

    rep = e.get("repeat")
    if not rep:
        return dia == base
    if rep == "daily":
        return True
    if rep == "weekdays":
        return dia.weekday() < 5
    if rep == "weekly":
        return (dia - base).days % 7 == 0
    if rep == "monthly":
        dia_efetivo = _dia_efetivo_mensal(base, dia)
        return dia.day == dia_efetivo
    return dia == base


def ocorrencias(e, wstart, wend):
    """Datetimes de inicio do evento dentro da janela [wstart, wend]."""
    hora = evento_inicio(e).time()
    out = []
    dia = wstart.date()
    while dia <= wend.date():
        if ocorre_no_dia(e, dia):
            occ = datetime.combine(dia, hora)
            if wstart <= occ <= wend:
                out.append(occ)
        dia += timedelta(days=1)
    return out


def expandir(eventos, wstart, wend):
    """Lista ordenada de (inicio, evento) na janela, expandindo recorrencias."""
    itens = [(occ, e) for e in eventos for occ in ocorrencias(e, wstart, wend)]
    itens.sort(key=lambda x: x[0])
    return itens


def formatar(e, ini):
    linha = f"  [{e['id']:>3}] {ini:%H:%M}"
    if e.get("dur"):
        fim = ini + timedelta(minutes=e["dur"])
        linha += f"-{fim:%H:%M}"
    linha += f"  {e['titulo']}"
    if e.get("repeat"):
        rep = e["repeat"]
        linha += f"  ({rep}{' ate ' + e.get('until') if e.get('until') else ''})"
    if e.get("desc"):
        linha += f"  — {e['desc']}"
    return linha


# -------------------------------------------------------------- Google Calendar
def get_google_service():
    """Autentica e retorna o serviço do Google Calendar."""
    if not GOOGLE_AVAILABLE:
        sys.exit("Bibliotecas do Google Calendar não instaladas. Execute: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    
    creds = None
    if GOOGLE_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_FILE), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # Token expirado ou revogado - remove o token para forçar nova autenticação
                if GOOGLE_TOKEN_FILE.exists():
                    GOOGLE_TOKEN_FILE.unlink()
                raise RefreshError("Token de autenticação Google expirado ou revogado. Execute a sincronização novamente para reautenticar.") from e
        else:
            if not GOOGLE_CREDENTIALS_FILE.exists():
                sys.exit(f"Arquivo de credenciais não encontrado: {GOOGLE_CREDENTIALS_FILE}. Baixe do Google Cloud Console.")
            flow = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        GOOGLE_TOKEN_FILE.write_text(creds.to_json())
    
    return build('calendar', 'v3', credentials=creds)


def event_to_google_event(e, occ):
    """Converte evento local para formato do Google Calendar."""
    # Garante que occ é um datetime, não apenas uma date
    if isinstance(occ, date) and not isinstance(occ, datetime):
        occ = datetime.combine(occ, time(9, 0))
    
    inicio = occ
    fim = inicio + timedelta(minutes=e["dur"]) if e.get("dur") else inicio + timedelta(hours=1)
    
     # Adiciona verificação para garantir que fim também é datetime
    if isinstance(fim, date) and not isinstance(fim, datetime):
        fim = datetime.combine(fim, time(17, 0))
    
    
    google_event = {
        'summary': e["titulo"],
        'start': {
            'dateTime': inicio.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
        'end': {
            'dateTime': fim.isoformat(),
            'timeZone': 'America/Sao_Paulo',
        },
    }
    
    if e.get("desc"):
        google_event['description'] = e["desc"]
    
    # Handle recurrence
    if e.get("repeat") and e["repeat"] != "none":
        rrule = []
        rep = e["repeat"]
        if rep == "daily":
            rrule.append("RRULE:FREQ=DAILY")
        elif rep == "weekdays":
            rrule.append("RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR")
        elif rep == "weekly":
            rrule.append("RRULE:FREQ=WEEKLY")
        elif rep == "monthly":
            rrule.append("RRULE:FREQ=MONTHLY")
        
        if e.get("until"):
            until_date = parse_data(e["until"])
            rrule.append(f"UNTIL={until_date.strftime('%Y%m%dT%H%M%SZ')}")
        
        if rrule:
            google_event['recurrence'] = rrule
    
    return google_event


def sync_event_to_google(e, occ=None):
    """Sincroniza um evento específico com o Google Calendar."""
    try:
        service = get_google_service()
        
        # Se não passou occ, usa a primeira ocorrência (para eventos recorrentes, cria a série)
        if occ is None:
            occ = evento_inicio(e)
        
        google_event = event_to_google_event(e, occ)
        
        # Se o evento já tem google_id, tenta atualizar
        if e.get("google_id"):
            try:
                # Primeiro, busca o evento existente para verificar o tipo
                existing = service.events().get(
                    calendarId=GOOGLE_CALENDAR_ID,
                    eventId=e["google_id"]
                ).execute()
                
                # Detecta tipos: se existe 'dateTime', é evento com hora; senão é all-day (date)
                novo_tem_hora = 'dateTime' in google_event['start']
                existente_tem_hora = 'dateTime' in existing['start']
                
                # Se o tipo mudou (date ↔ dateTime), deleta e recria
                if novo_tem_hora != existente_tem_hora:
                    print(f"  Tipo de evento mudou (all-day ↔ com hora), recriando...")
                    service.events().delete(
                        calendarId=GOOGLE_CALENDAR_ID,
                        eventId=e["google_id"]
                    ).execute()
                    # Recria como novo
                    created = service.events().insert(
                        calendarId=GOOGLE_CALENDAR_ID,
                        body=google_event
                    ).execute()
                    e["google_id"] = created['id']
                    return True, "recreated"
                
                # Senão, atualiza normalmente
                updated = service.events().update(
                    calendarId=GOOGLE_CALENDAR_ID,
                    eventId=e["google_id"],
                    body=google_event
                ).execute()
                e["google_id"] = updated['id']
                return True, "updated"
                
            except HttpError as error:
                if error.resp.status == 404:
                    # Evento não existe mais, cria novo
                    pass
                elif error.resp.status == 400 and 'eventTypeRestriction' in str(error):
                    # Erro de tipo de evento (não pode mudar date ↔ dateTime) - deleta e recria
                    print(f"  Não é possível mudar tipo do evento, recriando...")
                    try:
                        service.events().delete(
                            calendarId=GOOGLE_CALENDAR_ID,
                            eventId=e["google_id"]
                        ).execute()
                    except:
                        pass
                    # Remove google_id para criar como novo
                    e["google_id"] = None
                else:
                    raise
        
        # Cria novo evento
        created = service.events().insert(
            calendarId=GOOGLE_CALENDAR_ID,
            body=google_event
        ).execute()
        e["google_id"] = created['id']
        return True, "created"
        
    except RefreshError:
        # Re-lança para ser capturado no nível superior
        raise
    except Exception as ex:
        print(f"Erro ao sincronizar evento {e['id']} com Google Calendar: {ex}")
        return False, "error"


def delete_event_from_google(e):
    """Remove evento do Google Calendar."""
    if not e.get("google_id"):
        return True
    
    try:
        service = get_google_service()
        service.events().delete(
            calendarId=GOOGLE_CALENDAR_ID,
            eventId=e["google_id"]
        ).execute()
        return True
    except HttpError as error:
        if error.resp.status == 404:
            return True  # Já não existe
        print(f"Erro ao remover evento {e['id']} do Google Calendar: {error}")
        return False
    except RefreshError:
        raise
    except Exception as ex:
        print(f"Erro ao remover evento {e['id']} do Google Calendar: {ex}")
        return False


def get_google_events(service, time_min=None, time_max=None):
    """Busca eventos do Google Calendar."""
    try:
        events_result = service.events().list(
            calendarId=GOOGLE_CALENDAR_ID,
            timeMin=time_min.isoformat() + 'Z' if time_min else None,
            timeMax=time_max.isoformat() + 'Z' if time_max else None,
            singleEvents=True,
            orderBy='startTime',
            maxResults=2500
        ).execute()
        return events_result.get('items', [])
    except RefreshError:
        raise
    except Exception as ex:
        print(f"Erro ao buscar eventos do Google Calendar: {ex}")
        return []


def find_local_event_by_google_id(eventos, google_id):
    """Encontra evento local pelo google_id."""
    for e in eventos:
        if e.get("google_id") == google_id:
            return e
    return None


def sync_all_to_google():
    """Sincroniza todos os eventos locais para o Google Calendar.
    Retorna: (eventos_exportados, erros)
    eventos_exportados = lista de dicts com info dos eventos NOVAMENTE CRIADOS no Google
    """
    if not GOOGLE_AVAILABLE:
        print("Bibliotecas do Google Calendar não instaladas.")
        return [], 0
    
    eventos = carregar()
    service = get_google_service()
    
    # Busca eventos existentes no Google para saber quais já existem lá
    google_events = get_google_events(service)
    google_ids_remotos = {ge['id'] for ge in google_events}
    
    exportados = []
    errors = 0
    
    for e in eventos:
        # Tenta sincronizar: se tem google_id e ele existe no Google, atualiza; senão cria novo
        success, action = sync_event_to_google(e)
        if success:
            # Só adiciona à lista de exportados se foi CRIADO (não se foi apenas atualizado)
            if action == "created":
                exportados.append({
                    "id": e["id"],
                    "titulo": e["titulo"],
                    "inicio": e["inicio"],
                    "google_id": e["google_id"],
                    "action": action
                })
        else:
            errors += 1
    
    if exportados or errors > 0:
        salvar(eventos)
    
    print(f"Exportação para Google concluída: {len(exportados)} eventos novos, {errors} erros.")
    return exportados, errors


def sync_from_google():
    """Busca eventos do Google Calendar que não estão na agenda local e adiciona.
    Retorna: (eventos_importados, erros)
    eventos_importados = lista de eventos do Google que foram importados
    """
    if not GOOGLE_AVAILABLE:
        print("Bibliotecas do Google Calendar não instaladas.")
        return [], 0
    
    eventos = carregar()
    service = get_google_service()
    
    # Busca eventos do Google dos últimos 2 anos até 2 anos no futuro
    time_min = datetime.now() - timedelta(days=730)
    time_max = datetime.now() + timedelta(days=730)
    
    google_events = get_google_events(service, time_min, time_max)
    
    importados = []
    errors = 0
    
    for ge in google_events:
        # Verifica se já existe localmente pelo google_id
        if find_local_event_by_google_id(eventos, ge['id']):
            continue  # Já existe localmente
        
        # Converte evento do Google para formato local
        start = ge['start'].get('dateTime', ge['start'].get('date'))
        end = ge['end'].get('dateTime', ge['end'].get('date'))
        
        try:
            if 'T' in start:
                inicio_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            else:
                inicio_dt = datetime.fromisoformat(start + 'T00:00:00')
            
            if 'T' in end:
                fim_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
            else:
                fim_dt = datetime.fromisoformat(end + 'T23:59:59')
            
            dur = int((fim_dt - inicio_dt).total_seconds() / 60)
            
            # Detecta recorrência
            repeat = None
            until = None
            if 'recurrence' in ge:
                for rule in ge['recurrence']:
                    if rule.startswith('RRULE:'):
                        rrule = rule[6:]
                        if 'FREQ=DAILY' in rrule and 'BYDAY' not in rrule:
                            repeat = 'daily'
                        elif 'FREQ=WEEKLY' in rrule and 'BYDAY=MO,TU,WE,TH,FR' in rrule:
                            repeat = 'weekdays'
                        elif 'FREQ=WEEKLY' in rrule:
                            repeat = 'weekly'
                        elif 'FREQ=MONTHLY' in rrule:
                            repeat = 'monthly'
                        
                        if 'UNTIL=' in rrule:
                            until_str = rrule.split('UNTIL=')[1].split(';')[0]
                            try:
                                until = datetime.strptime(until_str, '%Y%m%dT%H%M%SZ').date().isoformat()
                            except:
                                pass
            
            evento = {
                "id": proximo_id(eventos),
                "titulo": ge.get('summary', 'Sem título'),
                "inicio": inicio_dt.strftime(FMT),
                "dur": dur if dur > 0 else None,
                "desc": ge.get('description'),
                "repeat": repeat,
                "until": until,
                "google_id": ge['id']
            }
            eventos.append(evento)
            importados.append({
                "id": evento["id"],
                "titulo": evento["titulo"],
                "inicio": evento["inicio"],
                "google_id": ge['id']
            })
        except Exception as ex:
            print(f"Erro ao converter evento do Google: {ex}")
            errors += 1
    
    if importados:
        salvar(eventos)
        print(f"{len(importados)} eventos importados do Google Calendar.")
    else:
        print("Nenhum evento novo para importar do Google Calendar.")
    
    return importados, errors


def sync_all_and_get_results():
    """
    Sincroniza eventos com Google Calendar (bidirecional) e retorna resultados detalhados.
    Retorna: (status_msg, exportados, importados)
    - exportados: lista de eventos locais NOVAMENTE CRIADOS no Google
    - importados: lista de eventos do Google importados para o local
    """
    if not GOOGLE_AVAILABLE:
        return "Bibliotecas do Google Calendar não instaladas.", [], []
    
    if not GOOGLE_CREDENTIALS_FILE.exists():
        return "Arquivo de credenciais não encontrado.", [], []
    
    print("Sincronizando com Google Calendar...")
    
    try:
        # 1. Exporta eventos locais para o Google
        print("Enviando eventos locais para Google Calendar...")
        exportados, export_errors = sync_all_to_google()
        
        # 2. Importa eventos do Google que não estão no local
        print("Buscando eventos do Google Calendar não presentes localmente...")
        importados, import_errors = sync_from_google()
        
        total_errors = export_errors + import_errors
        msg = "Sincronização concluída com sucesso!" if total_errors == 0 else f"Sincronização concluída com {total_errors} erro(s)."
        
        return msg, exportados, importados
    except RefreshError as e:
        # Token expirado ou revogado
        error_msg = "Não foi possível sincronizar, token de autenticação Google expirado"
        print(f"Erro de autenticação: {e}")
        return error_msg, [], []


# ------------------------------------------------------------------------ main
def cmd_new(args):
    eventos = carregar()
    inicio = parse_dt(args.at)
    until = args.until
    if until:
        parse_data(until)  # valida formato
        validar_until(until, inicio)  # valida contra data de início
    evento = {
        "id": proximo_id(eventos),
        "titulo": args.titulo,
        "inicio": inicio.strftime(FMT),
        "dur": args.dur,
        "desc": args.desc,
        "repeat": None if args.repeat == "none" else args.repeat,
        "until": until,
    }
    eventos.append(evento)
    salvar(eventos)
    print(f"Evento criado: [{evento['id']}] {evento['titulo']} em {evento['inicio']}"
          + (f" (repete {evento['repeat']})" if evento["repeat"] else ""))
    
    # Sincroniza com Google Calendar se disponível
    if GOOGLE_AVAILABLE and GOOGLE_CREDENTIALS_FILE.exists():
        if sync_event_to_google(evento)[0]:
            salvar(eventos)
            print("Evento sincronizado com Google Calendar.")
        else:
            print("Aviso: evento criado localmente, mas falha ao sincronizar com Google Calendar.")


def cmd_edit(args):
    eventos = carregar()
    evento = next((e for e in eventos if e["id"] == args.id), None)
    if evento is None:
        sys.exit(f"Evento {args.id} nao encontrado.")

    # Determina a nova data de início (se alterada) para validação do --until
    novo_inicio = parse_dt(args.at) if args.at is not None else evento_inicio(evento)
    novo_until = args.until if args.until is not None else evento.get("until")

    # Valida --until contra a data de início (nova ou existente)
    if novo_until is not None and novo_until not in ("", "none"):
        validar_until(novo_until, novo_inicio)

    if args.titulo is not None:
        evento["titulo"] = args.titulo
    if args.at is not None:
        evento["inicio"] = novo_inicio.strftime(FMT)
    if args.dur is not None:
        evento["dur"] = None if args.dur < 0 else args.dur
    if args.desc is not None:
        evento["desc"] = args.desc or None
    if args.repeat is not None:
        evento["repeat"] = None if args.repeat == "none" else args.repeat
    if args.until is not None:
        evento["until"] = None if args.until in ("", "none") else str(parse_data(args.until))

    salvar(eventos)
    print(f"Evento {args.id} atualizado.")
    print(formatar(evento, evento_inicio(evento)))
    
    # Sincroniza com Google Calendar se disponível
    if GOOGLE_AVAILABLE and GOOGLE_CREDENTIALS_FILE.exists():
        if sync_event_to_google(evento)[0]:
            salvar(eventos)
            print("Evento sincronizado com Google Calendar.")
        else:
            print("Aviso: evento atualizado localmente, mas falha a sincronizar com Google Calendar.")


def cmd_list(args):
    eventos = carregar()
    agora = datetime.now()

    if args.hours is not None:
        wstart, wend = agora, agora + timedelta(hours=args.hours)
        titulo = f"Proximas {args.hours}h ({agora:%d/%m %H:%M} → {wend:%d/%m %H:%M})"
    else:
        dia = parse_data(args.date) if args.date else agora.date()
        wstart = datetime.combine(dia, time.min)
        wend = datetime.combine(dia, time.max)
        titulo = f"Eventos de {dia:%d/%m/%Y}"

    itens = expandir(eventos, wstart, wend)
    print(titulo)
    if not itens:
        print("  (nenhum evento)")
    for occ, e in itens:
        print(formatar(e, occ))


def cmd_alerts(args):
    agora = datetime.now()
    max_min = max(ALERTAS_MIN)
    janela = expandir(carregar(), agora, agora + timedelta(minutes=max_min))
    if not janela:
        print(f"Nenhum evento nos proximos {max_min} minutos.")
        return
    print(f"⏰ Eventos iniciando nos proximos {max_min} minutos:")
    for occ, e in janela:
        faltam = int((occ - agora).total_seconds() // 60)
        # Determina qual alerta se aplica
        alerta_tipo = ""
        for am in ALERTAS_MIN:
            if faltam <= am:
                alerta_tipo = f" (alerta {am} min)"
                break
        print(f"  [{e['id']}] {e['titulo']} em {faltam} min ({occ:%H:%M}){alerta_tipo}")


def cmd_watch(args):
    import time as _time

    print(f"Monitorando eventos (alertas {', '.join(str(m) for m in ALERTAS_MIN)} min antes). Ctrl+C para sair.")
    # Chave: (event_id, occ_isoformat, alerta_min)
    avisados = set()
    try:
        while True:
            agora = datetime.now()
            max_min = max(ALERTAS_MIN)
            for occ, e in expandir(carregar(), agora, agora + timedelta(minutes=max_min)):
                faltam = int((occ - agora).total_seconds() // 60)
                for am in ALERTAS_MIN:
                    if faltam <= am:
                        chave = (e["id"], occ.isoformat(), am)
                        if chave not in avisados:
                            print(f"⏰ ALERTA {am} min: '{e['titulo']}' inicia em {faltam} min ({occ:%H:%M})",
                                  flush=True)
                            beep()
                            avisados.add(chave)
            _time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")


def cmd_rm(args):
    eventos = carregar()
    evento = next((e for e in eventos if e["id"] == args.id), None)
    if evento is None:
        sys.exit(f"Evento {args.id} nao encontrado.")
    
    # Remove do Google Calendar primeiro
    if GOOGLE_AVAILABLE and GOOGLE_CREDENTIALS_FILE.exists() and evento.get("google_id"):
        delete_event_from_google(evento)
    
    novos = [e for e in eventos if e["id"] != args.id]
    salvar(novos)
    print(f"Evento {args.id} removido.")


def cmd_sync(args):
    """Sincroniza eventos com Google Calendar (bidirecional)."""
    if not GOOGLE_AVAILABLE:
        sys.exit("Bibliotecas do Google Calendar não instaladas. Execute: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    
    if not GOOGLE_CREDENTIALS_FILE.exists():
        sys.exit(f"Arquivo de credenciais não encontrado. Baixe do Google Cloud Console.")
    
    print("Sincronizando com Google Calendar...")
    
    # Primeiro: envia eventos locais para o Google
    print("Enviando eventos locais para Google Calendar...")
    sync_all_to_google()
    
    # Segundo: busca eventos do Google que não estão na agenda local e adiciona.
    print("Buscando eventos do Google Calendar não presentes localmente...")
    sync_from_google()
    
    print("Sincronização concluída.")


# ------------------------------------------------------------------------ main
def main():
    p = argparse.ArgumentParser(description="Agenda de eventos simples.")
    sub = p.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("new", help="cria um evento")
    n.add_argument("titulo")
    n.add_argument("--at", required=True, help="inicio: 'YYYY-MM-DD HH:MM' ou 'HH:MM'")
    n.add_argument("--dur", type=int, default=None, help="duracao em minutos")
    n.add_argument("--desc", default=None, help="descricao")
    n.add_argument("--repeat", choices=REPEATS, default="none",
                   help="recorrencia: daily, weekdays, weekly, monthly")
    n.add_argument("--until", default=None, help="repete ate 'YYYY-MM-DD' (opcional)")
    n.set_defaults(func=cmd_new)

    e = sub.add_parser("edit", help="edita um evento (so os campos informados)")
    e.add_argument("id", type=int)
    e.add_argument("--titulo", default=None)
    e.add_argument("--at", default=None, help="novo inicio")
    e.add_argument("--dur", type=int, default=None, help="duracao em min (negativo = remove)")
    e.add_argument("--desc", default=None, help="descricao (vazio = remove)")
    e.add_argument("--repeat", choices=REPEATS, default=None)
    e.add_argument("--until", default=None, help="'YYYY-MM-DD' ou 'none' para remover")
    e.set_defaults(func=cmd_edit)

    l = sub.add_parser("list", help="lista eventos")
    l.add_argument("--date", help="dia especifico 'YYYY-MM-DD'")
    l.add_argument("--hours", type=int, nargs="?", const=6,
                   help="proximas N horas (padrao 6 se sem valor)")
    l.set_defaults(func=cmd_list)

    a = sub.add_parser("alerts", help="eventos nos proximos 60 min")
    a.set_defaults(func=cmd_alerts)

    w = sub.add_parser("watch", help="monitora e avisa (beep) 60, 30 e 15 min antes")
    w.add_argument("--interval", type=int, default=60, help="segundos entre checagens")
    w.set_defaults(func=cmd_watch)

    r = sub.add_parser("rm", help="remove um evento")
    r.add_argument("id", type=int)
    r.set_defaults(func=cmd_rm)

    s = sub.add_parser("sync", help="sincroniza eventos com Google Calendar")
    s.set_defaults(func=cmd_sync)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
