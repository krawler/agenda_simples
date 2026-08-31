import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("ideias.db")


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ideias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(255) NOT NULL,
                descricao TEXT NULL
            )
            """
        )
        conn.commit()


def validar_nome(nome):
    if nome is None:
        raise ValueError("O nome da ideia é obrigatório.")
    nome_limpo = str(nome).strip()
    if not nome_limpo:
        raise ValueError("O nome da ideia é obrigatório.")
    return nome_limpo


def criar_ideia(nome, descricao=None):
    nome_limpo = validar_nome(nome)
    descricao_limpa = None if descricao is None else str(descricao).strip() or None

    with _get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO ideias (nome, descricao) VALUES (?, ?)",
            (nome_limpo, descricao_limpa),
        )
        conn.commit()
        return buscar_ideia_por_id(cursor.lastrowid)


def listar_ideias():
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT id, nome, descricao FROM ideias ORDER BY id ASC"
        ).fetchall()
        return [dict(row) for row in rows]


def buscar_ideia_por_id(ideia_id):
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT id, nome, descricao FROM ideias WHERE id = ?",
            (ideia_id,),
        ).fetchone()
        return None if row is None else dict(row)


def atualizar_ideia(ideia_id, nome=None, descricao=None):
    ideia = buscar_ideia_por_id(ideia_id)
    if ideia is None:
        raise ValueError(f"Ideia {ideia_id} não encontrada.")

    novo_nome = ideia["nome"] if nome is None else validar_nome(nome)
    nova_descricao = ideia["descricao"] if descricao is None else (
        None if descricao is None else str(descricao).strip() or None
    )

    with _get_connection() as conn:
        conn.execute(
            "UPDATE ideias SET nome = ?, descricao = ? WHERE id = ?",
            (novo_nome, nova_descricao, ideia_id),
        )
        conn.commit()

    return buscar_ideia_por_id(ideia_id)


def remover_ideia(ideia_id):
    with _get_connection() as conn:
        cursor = conn.execute("DELETE FROM ideias WHERE id = ?", (ideia_id,))
        conn.commit()
        return cursor.rowcount > 0


init_db()
