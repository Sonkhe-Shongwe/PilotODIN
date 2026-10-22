"""Regression smoke checks for full-project Studio handoff and migration."""
import sqlite3
from pathlib import Path
from Migrate_From_Old_PilotODIN import migrate

ROOT=Path(__file__).resolve().parents[1]

def test_studio_app_sources():
    src=ROOT/'frontend'/'src'
    assert (src/'StudioHome.tsx').is_file()
    assert (src/'StudioAssistant.tsx').is_file()
    assert (src/'studio.css').is_file()
    assert "import './studio.css'" in (src/'main.tsx').read_text()
    text=(src/'App.tsx').read_text()
    for token in ('StudioHome','StudioAssistant','QualityWorkspace','ExploreWorkspace','AISettings','EvaluationDetails'):
        assert token in text

def test_migrate_preserves_source_and_rewrites_dataset_path(tmp_path):
    old=tmp_path/'previous'; dest=tmp_path/'new'
    (old/'data'/'datasets').mkdir(parents=True)
    (dest/'backend').mkdir(parents=True)
    (dest/'backend'/'main.py').write_text('')
    (old/'data'/'datasets'/'data.csv').write_text('a,b\n1,2\n')
    (old/'data'/'ai_secrets.dpapi').write_bytes(b'encrypted-placeholder')
    old_path=str(old/'data'/'datasets'/'data.csv')
    with sqlite3.connect(old/'data'/'pilotodin.sqlite3') as con:
        con.execute('CREATE TABLE projects (id TEXT,dataset_path TEXT)')
        con.execute('CREATE TABLE experiments (id TEXT)')
        con.execute('INSERT INTO projects VALUES (?,?)',('test_id',old_path))
        con.execute('INSERT INTO experiments VALUES (?)',('test_exp',))
    assert migrate(old,dest)==(1,1)
    with sqlite3.connect(dest/'data'/'pilotodin.sqlite3') as con:
        imported=con.execute('SELECT dataset_path FROM projects').fetchone()[0]
    assert imported==str((dest/'data'/'datasets'/'data.csv').resolve())
    assert Path(imported).is_file()
    assert (dest/'data'/'ai_secrets.dpapi').read_bytes()==b'encrypted-placeholder'
    with sqlite3.connect(old/'data'/'pilotodin.sqlite3') as con:
        assert con.execute('SELECT dataset_path FROM projects').fetchone()[0]==old_path

def test_migrate_refuses_overwrite(tmp_path):
    import pytest
    old=tmp_path/'previous';dest=tmp_path/'new'
    (old/'data').mkdir(parents=True)
    (old/'data'/'pilotodin.sqlite3').write_bytes(b'file')
    (dest/'backend').mkdir(parents=True)
    (dest/'backend'/'main.py').write_text('')
    (dest/'data').mkdir(parents=True)
    (dest/'data'/'keep.txt').write_text('do not touch')
    with pytest.raises(ValueError, match='not empty'):
        migrate(old,dest)
    assert (dest/'data'/'keep.txt').read_text()=='do not touch'
