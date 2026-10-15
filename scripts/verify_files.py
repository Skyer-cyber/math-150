"""Verify the exact PDF inventory without accessing the network."""

import hashlib
import json
from pathlib import Path
import sys


def verify(root):
    manifest = json.loads((root / 'MANIFEST.json').read_text())
    failures = []
    entries = list(manifest['files'])
    economics_path = root / '经济学150' / 'MANIFEST.json'
    if economics_path.is_file():
        economics = json.loads(economics_path.read_text())
        for source in economics['sources']:
            for part in source['parts']:
                entries.append({'path': part['repository_path'], 'bytes': part['bytes'], 'sha256': part['sha256']})
    for entry in entries:
        path = root / entry['path']
        if not path.is_file():
            failures.append({'path': entry['path'], 'error': 'missing'})
            continue
        data = path.read_bytes()
        actual = {
            'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
            'git_blob_sha1': hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest(),
        }
        for key, value in actual.items():
            if key in entry and entry[key] != value:
                failures.append({'path': entry['path'], 'error': key})
    expected = {e['path'] for e in entries}
    found = {p.relative_to(root).as_posix() for p in root.rglob('*.pdf') if '.git' not in p.parts}
    if expected != found:
        failures.append({'inventory_difference': sorted(expected ^ found)})
    return {'pdf_count': len(expected), 'verified': len(expected) - len({f.get('path') for f in failures if f.get('path')}), 'failures': failures}


if __name__ == '__main__':
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    result = verify(root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['failures']))
