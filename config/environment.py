"""Minimal local .env loader; values are never logged or returned."""
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def load_dotenv(path=ROOT/'.env'):
    if not path.is_file(): return False
    for number,raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
        line=raw.strip()
        if not line or line.startswith('#'): continue
        if line.startswith('export '): line=line[7:].lstrip()
        if '=' not in line: raise RuntimeError(f'.env inválido na linha {number}')
        key,value=line.split('=',1);key=key.strip();value=value.strip()
        if not key.replace('_','a').isalnum() or key[0].isdigit():
            raise RuntimeError(f'Nome inválido no .env, linha {number}')
        if len(value)>=2 and value[0]==value[-1] and value[0] in "'\"": value=value[1:-1]
        os.environ.setdefault(key,value)
    return True
