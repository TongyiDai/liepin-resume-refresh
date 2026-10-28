#!/usr/bin/env python3
"""Build a deterministic installable skill archive from Git-tracked files."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import zipfile


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if not re.fullmatch(r'v\d+\.\d+\.\d+',args.version):
        parser.error('Use a version such as v1.0.0')
    root=Path(__file__).resolve().parent.parent
    files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
    if 'SKILL.md' not in files:
        parser.error('Stage the release files in Git first')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    archive=args.output_dir/f'liepin-resume-refresh-{args.version}.zip'
    forbidden={'config.json','state.json','click.json','events.jsonl','initial-binding.json','run.lock'}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as output:
        for name in sorted(filter(None,files)):
            path=root/name
            if path.name in forbidden or any(part in {'.git','__pycache__','node_modules','dist','work','outputs'} for part in path.parts):
                raise ValueError('Private or generated file found in release index')
            info=zipfile.ZipInfo('liepin-resume-refresh/'+name,(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            output.writestr(info,path.read_bytes())
    print(archive.name)


if __name__=='__main__':
    main()
