#!/usr/bin/env python3
"""Check package structure, local README assets, and obvious private data."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET


def main():
    root=Path(__file__).resolve().parent.parent
    files=[name for name in subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0') if name]
    skill=(root/'SKILL.md').read_text(encoding='utf-8')
    assert skill.startswith('---\n') and re.search(r'^name: liepin-resume-refresh$',skill,re.M)
    assert re.search(r'^description: .+',skill,re.M)
    assert len(skill.splitlines())<=500
    assert (root/'LICENSE').is_file()
    forbidden={'config.json','state.json','click.json','events.jsonl','initial-binding.json','run.lock'}
    patterns=[re.compile(r'\b(?:ghp|gho|ghs|github_pat)_[A-Za-z0-9_-]{20,}\b'),re.compile(r'-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----'),re.compile('/'+'Users/'+r'[^\s"\']+'),re.compile('/'+'home/'+r'[^\s"\']+')]
    for name in files:
        path=root/name
        assert path.name not in forbidden, name
        if path.suffix in {'.py','.md','.mjs','.json','.yaml','.yml','.svg'}:
            text=path.read_text(encoding='utf-8')
            assert not any(pattern.search(text) for pattern in patterns), name
        if path.suffix=='.svg':
            ET.parse(path)
    readme=(root/'README.md').read_text(encoding='utf-8')
    assert readme.lstrip().startswith('>')
    assets=re.findall(r'<img[^>]+src="(assets/[^"?]+)',readme)
    assert len([name for name in assets if name.endswith('.svg')])>=3
    assert all((root/name).is_file() for name in assets)
    print(f'Package checks passed: {len(files)} tracked files, {len(assets)} README assets')


if __name__=='__main__':
    main()
