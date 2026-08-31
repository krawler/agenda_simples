import sqlite3
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import ideias
import renderers


class TestIdeiasSqlite(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "ideias_test.db"
        ideias.DB_PATH = self.db_path
        ideias.init_db()

    def tearDown(self):
        try:
            if self.db_path.exists():
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.execute("PRAGMA wal_checkpoint(FULL)")
                except Exception:
                    pass
                self.db_path.unlink(missing_ok=True)
        except PermissionError:
            pass
        except OSError:
            pass
        try:
            shutil.rmtree(self.temp_dir.name, ignore_errors=True)
        except Exception:
            pass

    def test_tabela_ideias_existe(self):
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ideias'"
            ).fetchall()
        self.assertEqual(rows, [("ideias",)])

    def test_criar_e_listar_ideia(self):
        item = ideias.criar_ideia("Planejar app", "Criar app para clientes")

        self.assertEqual(item["id"], 1)
        self.assertEqual(item["nome"], "Planejar app")
        self.assertEqual(item["descricao"], "Criar app para clientes")

        itens = ideias.listar_ideias()
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0]["nome"], "Planejar app")

    def test_nome_obrigatorio(self):
        with self.assertRaises(ValueError):
            ideias.criar_ideia("  ", "descricao")

    def test_descricao_pode_ser_none(self):
        item = ideias.criar_ideia("Nova ideia")
        self.assertIsNone(item["descricao"])

    def test_buscando_ideia_por_id(self):
        criada = ideias.criar_ideia("Estudar Python", "Aprender testes")
        encontrada = ideias.buscar_ideia_por_id(criada["id"])

        self.assertIsNotNone(encontrada)
        self.assertEqual(encontrada["nome"], "Estudar Python")

    def test_render_page_contem_secao_ideias(self):
        html = renderers.render_page(date.today())

        self.assertIn('id="ideas-plans-panel"', html)
        self.assertIn('Ideias e planos', html)


if __name__ == "__main__":
    unittest.main()
