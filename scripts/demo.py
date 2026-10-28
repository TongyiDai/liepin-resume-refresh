#!/usr/bin/env python3
"""Offline demonstration of the real daily guard, using a simulated browser."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import refresh
from test_refresh import NOW, binding


def simulated_browser(config, home, dry_run, now):
    if dry_run:
        return {"status":"ready","attempted":False,"verified":False}
    refresh.write_json(home/'click.json',{'day':now.date().isoformat(),'at':now.isoformat()})
    return {"status":"success","attempted":True,"verified":True,"evidence":"simulated_browser"}


def main():
    print('OFFLINE DEMO | simulated browser | no account or scheduler access\n')
    with tempfile.TemporaryDirectory() as temporary,patch.object(refresh,'browser_run',side_effect=simulated_browser),patch.object(refresh,'notify'):
        home=Path(temporary)
        refresh.write_json(home/'config.json',{'schema_version':1,'enabled':True,'scheduler_mode':'agent','daily_time':'09:03','browser':'ego','binding':binding()})
        for label,dry in [('1. AI checks the bound resume',True),('2. Daily task refreshes once',False),('3. Another trigger on the same day',False)]:
            result=refresh.run_once(home,dry_run=dry,scheduled=not dry,now=NOW)
            print(label)
            print('   '+json.dumps({key:result.get(key) for key in ('status','attempted','verified')}))
            print()
        config=refresh.config_for(home)
        config['enabled']=False
        refresh.write_json(home/'config.json',config)
        result=refresh.run_once(home,scheduled=True,now=NOW)
        print('4. User pauses the task')
        print('   '+json.dumps(result))


if __name__=='__main__':
    main()
