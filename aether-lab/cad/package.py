"""Portable CAD bundles. Hashes detect corruption, not malicious authorship."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile

FORMAT = 'aether-cad-package/1'
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_ARCHIVE = 128 * 1024 * 1024
MAX_FILES = 514
_EXT = re.compile(r'external/[A-Za-z0-9_-]+\.brep\Z')
_SHEET = re.compile(r'source_sheet\.(png|jpg|jpeg|webp|gif)\Z')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs)


def _external(data):
    result = {}
    for feature in data.get('features', []):
        if feature.get('op') == 'external_brep':
            p = feature.get('params', {})
            name, digest = p.get('brep_file'), p.get('sha256')
            if not isinstance(name, str) or not _EXT.fullmatch(name) or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('unsafe or invalid external B-rep reference')
            if name in result and result[name] != digest:
                raise ValueError('conflicting external B-rep hashes')
            result[name] = digest
    return result


def write(doc, sheet, dest):
    data = doc.data
    members = {'model.aethercad': doc.to_json().encode('utf-8')}
    root = Path(doc.base_dir).resolve() if getattr(doc, 'base_dir', None) else None
    for name, digest in _external(data).items():
        if root is None:
            raise ValueError('document has no external B-rep directory')
        p = (root / name).resolve()
        if not p.is_relative_to(root) or not p.is_file():
            raise ValueError('external B-rep is missing or outside document directory')
        if p.stat().st_size > MAX_FILE:
            raise ValueError('external B-rep too large')
        members[name] = p.read_bytes()
        if _hash(members[name]) != digest:
            raise ValueError('external B-rep hash mismatch')
    sheet_name = None
    if sheet:
        p = Path(sheet)
        ext = p.suffix.lower()
        sheet_name = 'source_sheet' + ext
        if not _SHEET.fullmatch(sheet_name) or p.stat().st_size > MAX_FILE:
            raise ValueError('unsupported or oversized source sheet')
        content = p.read_bytes()
        if _hash(content) != data.get('source', {}).get('sha256'):
            raise ValueError('source sheet no longer matches document')
        members[sheet_name] = content
    if len(members) + 1 > MAX_FILES or any(len(x) > MAX_FILE for x in members.values()) or sum(map(len, members.values())) > MAX_TOTAL:
        raise ValueError('CAD package exceeds size limits')
    manifest = {'format': FORMAT, 'sheet': sheet_name, 'files': {n: _hash(b) for n, b in members.items()}}
    members['manifest.json'] = json.dumps(manifest, sort_keys=True).encode()
    dest = Path(dest)
    fd, temp = tempfile.mkstemp(prefix='.package-', dir=dest.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, blob in members.items():
                z.writestr(name, blob)
        os.replace(temp, dest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read(path, staging):
    """Validate every member and dependency before writing known names to an empty staging directory."""
    if os.path.getsize(path) > MAX_ARCHIVE:
        raise ValueError('CAD package archive too large')
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(names) > MAX_FILES or len(names) != len(set(names)):
            raise ValueError('duplicate or excessive package members')
        if 'manifest.json' not in names or 'model.aethercad' not in names:
            raise ValueError('package manifest or CAD document missing')
        for i in infos:
            if not (i.filename in ('manifest.json', 'model.aethercad') or _EXT.fullmatch(i.filename) or _SHEET.fullmatch(i.filename)):
                raise ValueError('invalid package member name')
            if i.is_dir() or stat.S_ISLNK(i.external_attr >> 16) or i.flag_bits & 1 or i.file_size > MAX_FILE:
                raise ValueError('unsupported or oversized package member')
        if sum(i.file_size for i in infos) > MAX_TOTAL:
            raise ValueError('CAD package exceeds uncompressed size limit')
        manifest = _json(z.read('manifest.json'))
        if not isinstance(manifest, dict) or manifest.get('format') != FORMAT or not isinstance(manifest.get('files'), dict):
            raise ValueError('invalid package manifest')
        files = manifest['files']
        if set(files) != set(names) - {'manifest.json'}:
            raise ValueError('manifest does not match package members')
        sheet = manifest.get('sheet')
        sheets = [n for n in files if _SHEET.fullmatch(n)]
        if sheets != ([sheet] if sheet is not None else []):
            raise ValueError('invalid package source sheet')
        members = {}
        for name, digest in files.items():
            blob = z.read(name)
            if not isinstance(digest, str) or _hash(blob) != digest:
                raise ValueError('package member hash mismatch')
            members[name] = blob
    data = _json(members['model.aethercad'])
    external = _external(data)
    if set(external) != {n for n in members if _EXT.fullmatch(n)}:
        raise ValueError('external B-rep dependencies do not match document')
    for name, digest in external.items():
        if _hash(members[name]) != digest:
            raise ValueError('external B-rep hash mismatch')
    if sheet and (_hash(members[sheet]) != data.get('source', {}).get('sha256') or data.get('route', 'three_view') != 'three_view'):
        raise ValueError('source sheet does not match document')
    root = Path(staging)
    for name, blob in members.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    return data, str(root / sheet) if sheet else None
