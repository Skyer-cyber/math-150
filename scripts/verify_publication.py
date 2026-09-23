"""Check a fresh remote clone and write a local-only publication receipt."""

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from verify_files import verify

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'Skyer-cyber/math-150'


def command(*args, cwd=ROOT):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def api(endpoint):
    return json.loads(command('gh', 'api', endpoint))


clone = Path(sys.argv[1]).resolve()
head = command('git', 'rev-parse', 'HEAD')
assert command('git', 'rev-parse', 'HEAD', cwd=clone) == head, 'Clone must match final published commit'
assert command('git', 'status', '--porcelain') == '', 'Uncommitted changes remain'
metadata = api(f'repos/{REPOSITORY}')
assert metadata['private'] is True
assert api(f'repos/{REPOSITORY}/branches/main')['commit']['sha'] == head
local_check = verify(ROOT)
remote_check = verify(clone)
assert not local_check['failures'] and not remote_check['failures']
manifest = json.loads((ROOT / 'MANIFEST.json').read_text())
assert (ROOT / 'MANIFEST.json').read_bytes() == (clone / 'MANIFEST.json').read_bytes()
tree_response = api(f'repos/{REPOSITORY}/git/trees/{head}?recursive=1')
assert not tree_response.get('truncated')
tree = {entry['path']: entry for entry in tree_response['tree'] if entry['type'] == 'blob'}
assert {p for p in tree if p.endswith('.pdf')} == {entry['path'] for entry in manifest['files']}
for entry in manifest['files']:
    remote = tree[entry['path']]
    assert remote['size'] == entry['bytes'] and remote['sha'] == entry['git_blob_sha1']
    source = ROOT.parent / entry['path']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == entry['sha256']

tests = []
for revision, version, operation in [('33b69c0', 1, 'create'), ('6793591', 2, 'modify')]:
    commit = command('git', 'rev-parse', revision)
    response = api(f'repos/{REPOSITORY}/contents/_checks/local-write-test.txt?ref={commit}')
    text = base64.b64decode(response['content']).decode()
    assert text == f'math-150 local publication check\nversion={version}\noperation={operation}\n'
    tests.append({'operation': operation, 'commit': commit, 'remote_content_matches': True, 'blob_sha1': response['sha']})

comparison_path = ROOT / 'SOURCE_COMPARISON.json'
source_comparison = json.loads(comparison_path.read_text()) if comparison_path.exists() else {'cloud_catalog_comparison': 'unavailable', 'original_cloud_sha256_manifest': 'unavailable'}
receipt = {
    'schema_version': 1,
    'verified_at_utc': datetime.now(timezone.utc).isoformat(),
    'repository': REPOSITORY,
    'repository_url': metadata['html_url'],
    'private': True,
    'commit_sha': head,
    'local_directory': str(ROOT),
    'fresh_clone_directory': str(clone),
    'pdf_count': len(manifest['files']),
    'total_pdf_bytes': sum(entry['bytes'] for entry in manifest['files']),
    'original_project_count': manifest['original_project_count'],
    'supplemental_course_count': manifest['supplemental_course_count'],
    'added_workbook_count': manifest['added_workbook_count'],
    'fresh_clone_sha256_verification': remote_check,
    'remote_tree_sizes_and_blob_hashes_match': True,
    'local_sources_unchanged': True,
    'write_tests': tests,
    'source_comparison': source_comparison,
    'codex_github_connector': {'private_repository_read': 'passed', 'markdown_read': 'passed', 'pdf_utf8_read': 'failed_unicode_decode', 'write_not_tested': True},
    'chatgpt_web_permissions_changed': False,
    'chatgpt_project_files_automatically_synchronized': False,
}
(ROOT / 'PUBLISH_RECEIPT.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(receipt, ensure_ascii=False, indent=2))
