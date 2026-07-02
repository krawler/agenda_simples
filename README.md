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

## Notas

- O beep usa `winsound.Beep` no Windows (som audível de verdade) e `\a` (BEL) em
  outros sistemas.
- Recorrência `monthly` usa o dia do mês do evento base; meses sem esse dia
  (ex.: dia 31) simplesmente não têm ocorrência naquele mês.
