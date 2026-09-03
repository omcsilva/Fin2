"""Copy referenced Fin1 images to private storage; never modify Fin1."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--host', default='mcsil@rpi5.lan')
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    refs = set()
    with sqlite3.connect(args.snapshot.as_uri() + '?mode=ro', uri=True) as db:
        for kind in ('titular', 'moeda', 'instituicao', 'produto', 'conta', 'ativo'):
            refs.update(row[0] for row in db.execute(f'SELECT imagem FROM fin1_{kind}') if row[0])
    def fetch(ref):
        try:
            if ref.startswith('https://'):
                with urlopen(Request(ref, headers={'User-Agent': 'Fin2 catalog migration'}), timeout=20) as response:
                    data = response.read(5_000_001)
            elif re.fullmatch(r'[\w.-]+', ref):
                data = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', args.host,
                    'cat /home/mcsil/Fin1/fin1/static/img/' + ref], check=True, capture_output=True, timeout=25).stdout
            else:
                raise ValueError('unsupported reference')
            if len(data) > 5_000_000:
                raise ValueError('image too large')
            if data.startswith(b'\x89PNG\r\n\x1a\n'): mime = 'image/png'
            elif data.startswith(b'\xff\xd8\xff'): mime = 'image/jpeg'
            elif b'<svg' in data[:1000]: mime = 'image/svg+xml'
            else: raise ValueError('unsupported image format')
            digest = hashlib.sha256(data).hexdigest()
            (args.destination / digest).write_bytes(data)
            return ref, {'hash': digest, 'mime': mime}
        except Exception as exc:
            print(f'Unavailable: {ref}: {type(exc).__name__}')
            return ref, None
    path = args.destination / 'manifest.json'
    result = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for ref, entry in pool.map(fetch, sorted(refs)):
            if entry: result[ref] = entry
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)
    print(f'Available: {len(refs & result.keys())}/{len(refs)} references')


if __name__ == '__main__':
    main()
