# Agenda Simples

Agenda de eventos por linha de comando, em Python puro (sem dependências).
Os eventos ficam em `eventos.json`, ao lado do script.

## Uso

```bash
# Criar evento (data completa, ou só a hora = hoje)
python agenda.py new "Reuniao" --at "2026-07-01 15:00" --dur 60 --desc "com o time"
python agenda.py new "Cafe" --at "10:30"

# Eventos recorrentes: --repeat daily|weekdays|weekly|monthly  [--until YYYY-MM-DD]
python agenda.py new "Standup" --at "09:00" --repeat weekdays --dur 15
python agenda.py new "Pagamento" --at "2026-07-05 10:00" --repeat monthly --until 2026-12-31

# Editar (só os campos informados; --dur negativo remove duracao,
#          --desc "" remove descricao, --repeat none / --until none removem recorrencia)
python agenda.py edit 3 --at "16:30" --desc "remarcada"
python agenda.py edit 2 --repeat none

# Listar
python agenda.py list                    # eventos de hoje
python agenda.py list --date 2026-07-05  # eventos de uma data
python agenda.py list --hours            # proximas 6 horas (padrao)
python agenda.py list --hours 24         # proximas N horas

# Alertas: eventos iniciando nos proximos 30 min
python agenda.py alerts

# Monitorar em segundo plano (bipa/avisa 30 min antes)
python agenda.py watch                   # checa a cada 60s
python agenda.py watch --interval 30

# Remover evento pelo id
python agenda.py rm 3
```

## Interface web (opcional)

Um mini servidor em Python puro (`http.server`) que reaproveita toda a lógica
do `agenda.py` e serve uma página com **HTMX + Tailwind + daisyUI** (via CDN).
Calendário à esquerda, eventos do dia + formulário à direita.

```bash
python server.py            # abre em http://localhost:8000
python server.py --port 8080
```

- Clique num dia do calendário para ver os eventos daquele dia.
- Dias com eventos ganham um marcador; adicionar/editar/remover atualiza o
  calendário na hora (HTMX). Eventos recorrentes aparecem expandidos.
- **Editar** um evento pelo botão ✎ (formulário inline, preenchido).
- **Recorrentes** têm um menu (⋯) com: editar série, *pular este dia* (remove só
  aquela data) e remover a série inteira.
- **Seletor de tema** (daisyUI) no topo, com a escolha salva no navegador.
- Usa o mesmo `eventos.json` da CLI — as duas interfaces ficam em sincronia,
  inclusive as ocorrências puladas (campo `except`).

> Nota sobre Thymeleaf: é um motor de templates **Java/Spring** e não roda em
> Python. Para reaproveitar a lógica do `agenda.py` sem um backend Java à parte,
> a página é servida por este mini servidor Python. HTMX, Tailwind e daisyUI são
> só front-end e continuam exatamente como pedido.

## Lembretes por e-mail e Telegram (opcional)

`notificador.py` envia notificações **em dois horários**:
- **E-mail** 30 minutos antes (via SMTP)
- **Telegram** 90 minutos (1h30) antes (via API do bot)

Python puro (stdlib `smtplib`, `email`, `urllib`) e usa o mesmo `eventos.json`.
Email e Telegram são independentes — configure um, outro ou ambos.

### Configuração

Copie `.env.example` para `.env` e preencha (o `.env` fica fora do git):

#### E-mail

```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_app    # Gmail: gere em https://myaccount.google.com/apppasswords
SMTP_FROM=seu_email@gmail.com
AGENDA_EMAIL_TO=seu_email@gmail.com
```

#### Telegram

```
TELEGRAM_BOT_TOKEN=123456:ABCdefGHIjklmnoPQRstuvWXyz  # obtenha com @BotFather
TELEGRAM_CHAT_ID=1234567890       # seu ID de usuário ou grupo
```

Para descobrir seu **chat_id**:
1. Abra o Telegram e procure por `@BotFather`
2. Digite `/newbot` e crie seu bot (vai receber um token)
3. Escreva `/start` ao seu novo bot
4. Abra https://api.telegram.org/bot{SEU_TOKEN}/getUpdates e procure `"id"` em `chat`

Ou use um bot como `@userinfobot` para descobrir seu ID instantaneamente.

### Uso

```bash
# Testes
python notificador.py --test                  # e-mail de teste
python notificador.py --test-tg               # Telegram de teste
python notificador.py --dry-run --once        # mostra o que seria enviado (não envia)

# Produção
python notificador.py                         # serviço: checa a cada 60s
python notificador.py --once                  # checa uma vez e sai (Agendador/cron)
python notificador.py --interval 30           # intervalo customizado
```

- Instalar dependências Google na sua venv:
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib

- **Modo serviço** (`python notificador.py`): deixe rodando; verifica a cada 60s.
- **Modo `--once`**: ideal para agendar no **Agendador de Tarefas do Windows**
  (ou cron) a cada 5–15 min — sem processo fixo em segundo plano.
- Cada notificação é enviada **uma única vez** (registro em `enviados.json`), mesmo
  reiniciando o serviço. Eventos recorrentes recebem um lembrete por ocorrência.
- Falhas de conexão com Telegram não bloqueiam o serviço — será retentado no
  próximo ciclo.

## Notas

- O beep usa `winsound.Beep` no Windows (som audível de verdade) e `\a` (BEL) em
  outros sistemas.
- Recorrência `monthly` usa o dia do mês do evento base; meses sem esse dia
  (ex.: dia 31) simplesmente não têm ocorrência naquele mês.
