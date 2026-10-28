#!/usr/bin/env python3
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import refresh

NOW = dt.datetime(2026, 10, 28, 9, 3, tzinfo=dt.timezone(dt.timedelta(hours=8)))


def binding():
    return {
        "resume_url": "https://c.liepin.com/", "identity_selector": "#owner",
        "identity_sha256": hashlib.sha256(b"Example Candidate").hexdigest(),
        "resume_id_sha256": hashlib.sha256(b"fixture-resume").hexdigest(),
        "refresh_selector": "#refresh", "refresh_text": "刷新简历",
        "status_selector": "#status", "success_selector": "#success",
        "success_text": "刷新成功", "success_surface_selector": "#surface",
        "blocked_selector": None, "dismiss_selectors": [],
    }


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.config = {"schema_version": 1, "enabled": True, "daily_time": "09:03", "binding": binding(), "browser_executable": shutil.which("node")}
        refresh.write_json(self.home / "config.json", self.config)

    def tearDown(self):
        self.temp.cleanup()

    def test_calendar_day_prevents_second_click(self):
        refresh.write_json(self.home / "click.json", {"day": NOW.date().isoformat()})
        with patch.object(refresh, "browser_run") as browser:
            self.assertEqual(refresh.run_once(self.home, now=NOW)["status"], "skipped_today")
            browser.assert_not_called()

    def test_next_day_is_eligible(self):
        refresh.write_json(self.home / "click.json", {"day": "2026-10-27"})
        with patch.object(refresh, "browser_run", return_value={"status": "success", "verified": True}), patch.object(refresh, "notify"):
            result = refresh.run_once(self.home, now=NOW)
        self.assertEqual(result["status"], "success")

    def test_timeout_preserves_click_reservation(self):
        def timeout(config, home, dry_run, now):
            refresh.write_json(home / "click.json", {"day": now.date().isoformat()})
            return {"status": "browser_timeout", "attempted": False, "verified": False}
        with patch.object(refresh, "browser_run", side_effect=timeout), patch.object(refresh, "notify"):
            result = refresh.run_once(self.home, now=NOW)
            self.assertEqual(result["status"], "unverified")
            self.assertTrue(result["attempted"])
            self.assertEqual(refresh.run_once(self.home, now=NOW)["status"], "skipped_today")

    def test_dry_run_does_not_validate_install(self):
        with patch.object(refresh, "browser_run", return_value={"status": "ready", "attempted": False, "verified": False}):
            refresh.run_once(self.home, dry_run=True, now=NOW)
        with self.assertRaises(ValueError):
            refresh.schedule_install(self.home, self.config, "09:03")
        self.assertFalse((self.home / "click.json").exists())

    def test_stale_binding_cannot_install(self):
        refresh.write_json(self.home / "state.json", {"verified_binding": "other-binding"})
        with self.assertRaises(ValueError):
            refresh.schedule_install(self.home, self.config, "09:03")

    def test_browser_switch_invalidates_context(self):
        value = dict(self.config)
        value.update(browser="cdp",cdp_endpoint="http://127.0.0.1:9222")
        self.assertNotEqual(refresh.context_hash(self.config), refresh.context_hash(value))

    def test_read_only_current_target_today_can_validate(self):
        with patch.object(refresh, "browser_run", return_value={"status":"already_refreshed","verified":True,"attempted":False}):
            refresh.run_once(self.home, dry_run=True, now=NOW)
        state = refresh.read_json(self.home / "state.json")
        self.assertEqual(state["verified_context"], refresh.context_hash(self.config))
        self.assertFalse((self.home / "click.json").exists())

    def verified_state(self):
        refresh.write_json(self.home / "state.json", {"verified_binding":refresh.binding_hash(self.config["binding"]),"verified_context":refresh.context_hash(self.config)})

    def test_agent_schedule_requires_live_verification(self):
        with self.assertRaises(ValueError):
            refresh.record_agent_schedule(self.home,self.config,"fixture-job","09:03")

    def test_agent_schedule_saves_real_id_after_verification(self):
        self.verified_state()
        with patch.object(refresh,"schedule_status",return_value={"registered":False}),patch.object(refresh,"prepare_runtime",return_value=self.home/'skill/scripts/refresh.py'):
            result=refresh.record_agent_schedule(self.home,self.config,"fixture-job","09:03")
        saved=refresh.read_json(self.home/'config.json')
        self.assertTrue(result['saved'])
        self.assertEqual(saved['agent_job_id'],'fixture-job')
        self.assertEqual(saved['scheduler_mode'],'agent')
        self.assertTrue(saved['enabled'])

    def test_agent_schedule_rejects_existing_local_schedule(self):
        self.verified_state()
        with patch.object(refresh,"schedule_status",return_value={"registered":True}),self.assertRaises(ValueError):
            refresh.record_agent_schedule(self.home,self.config,"fixture-job","09:03")

    def test_local_schedule_rejects_existing_agent_schedule(self):
        self.config.update(scheduler_mode='agent',agent_job_id='fixture-job')
        self.verified_state()
        with self.assertRaises(ValueError):
            refresh.schedule_install(self.home,self.config,'09:03')

    def test_runtime_copy_excludes_git_metadata(self):
        target=refresh.prepare_runtime(self.home)
        self.assertTrue(target.is_file())
        self.assertFalse((self.home/'skill/.git').exists())

    def test_success_binds_verified_target(self):
        with patch.object(refresh, "browser_run", return_value={"status": "success", "verified": True, "attempted": True}), patch.object(refresh, "notify"):
            refresh.run_once(self.home, now=NOW)
        state = refresh.read_json(self.home / "state.json")
        self.assertEqual(state["verified_binding"], refresh.binding_hash(binding()))
        self.assertEqual(state["last_confirmed_day"], "2026-10-28")

    def test_pause_does_not_open_browser(self):
        self.config["enabled"] = False
        refresh.write_json(self.home / "config.json", self.config)
        with patch.object(refresh, "browser_run") as browser:
            self.assertEqual(refresh.run_once(self.home, scheduled=True, now=NOW)["status"], "paused")
            browser.assert_not_called()

    def test_ego_console_result_on_stderr(self):
        completed = subprocess.CompletedProcess([], 0, "", 'LIEPIN_RESULT {"status":"ready","attempted":false,"verified":false}\n')
        with patch.object(refresh.subprocess, "run", return_value=completed):
            result = refresh.browser_run(self.config, self.home, True, NOW)
        self.assertEqual(result["status"], "ready")

    def test_foreign_url_rejected(self):
        value = binding()
        value["resume_url"] = "https://c.liepin.com.example.test/"
        with self.assertRaises(ValueError):
            refresh.validate_binding(value)

    def test_same_name_requires_resume_identity(self):
        value = binding()
        value.pop("resume_id_sha256")
        with self.assertRaises(ValueError):
            refresh.validate_binding(value)

    def test_snapshot_refs_rejected(self):
        value = binding()
        value["refresh_selector"] = "@47"
        with self.assertRaises(ValueError):
            refresh.validate_binding(value)

    def test_macos_schedule_preserves_spaces_and_time(self):
        path = self.home / "candidate data"
        plan = refresh.scheduler_plan(path, "09:03", "darwin")["plist"]
        self.assertEqual(plan["StartCalendarInterval"], {"Hour": 9, "Minute": 3})
        self.assertIn(str(path), plan["ProgramArguments"])
        self.assertFalse(plan["RunAtLoad"])

    def test_windows_schedule_requires_interactive_session(self):
        command = refresh.scheduler_plan(self.home, "09:03", "win32")["create"]
        self.assertIn("/IT", command)
        self.assertEqual(command[command.index("/SC") + 1], "DAILY")
        self.assertEqual(command[command.index("/ST") + 1], "09:03")

    def test_windows_utf16_scheduler_response(self):
        xml='<Task><Arguments>fixture</Arguments></Task>'
        raw=subprocess.CompletedProcess([],0,xml.encode('utf-16'),b'')
        with patch.object(refresh.subprocess,'run',return_value=raw):
            result=refresh.execute(['fixture'])
        self.assertEqual(result.stdout,xml)

    def test_windows_xml_escaped_owner_path(self):
        home=self.home/'Candidate & Account'
        path=str(home/'skill/scripts/refresh.py')
        xml=f'<Task xmlns="urn:fixture"><Actions><Exec><Arguments>{html.escape(path)}</Arguments></Exec></Actions></Task>'
        self.assertTrue(refresh.owns_windows_task(xml,home))
        self.assertFalse(refresh.owns_windows_task(xml,self.home/'Another Account'))


FAKE_BROWSER = r'''
let phase = "before", clicks = 0, finished = false;
const node = (text, disabled=false) => ({textContent:text,disabled,getClientRects:()=>[1],hasAttribute:()=>false,getAttribute:()=>null});
globalThis.getComputedStyle = () => ({display:"block",visibility:"visible",pointerEvents:"auto"});
globalThis.location = {get href(){return phase === "after" && fixture.foreignAfter ? "https://example.test/" : "https://c.liepin.com/";}};
globalThis.document = {
 body:{get innerText(){return fixture.challenge ? "请完成验证" : "";}},
 querySelector(s){return this.querySelectorAll(s)[0]||null;},
 querySelectorAll(s){
  const after = phase === "after";
  if(s === '#owner') return [node(fixture.wrongOwner || (after && fixture.wrongAfter) ? 'Another Candidate' : 'Example Candidate')];
  if(s === '#refresh') return Array.from({length:fixture.ambiguous?2:1},()=>node('刷新简历',!!fixture.disabled));
  if(s === '#status') return [node(fixture.today || (after && fixture.changedTime) ? '刷新时间 2026-10-28' : '刷新时间 2026-10-27')];
  if(s === '#success') return fixture.staleSuccess || (after && fixture.notice) ? [node('刷新成功')] : [];
  if(s === '#surface') return after && fixture.surface ? [node('')] : [];
  if(s.includes('input[placeholder')) return fixture.login?[node('')]:[];
  if(s.includes('[role="dialog"]')) return fixture.paid?[node('立即开通 购买金卡')]:[];
  return [];
 }
};
async function taskSpace(){return {
 page(){return {
  async goto(){},
  async evaluate(fn,arg){return fn(arg);},
  async click(){clicks++; if(fixture.clickThrows) throw new Error(fixture.control?'EGO_USER_CONTROL':'Click interrupted'); phase='after';},
  async waitForFunction(fn,arg){if(!fn(arg)) throw new Error('Page wait timeout');},
  async waitForSelector(){},
  async events(){return phase==='before'?[{method:'Network.responseReceived',params:{requestId:'owner',response:{url:'https://api-c.liepin.com/api/com.liepin.usercx.pc.user.base-property'}}}]:fixture.noNative?[]:[{method:'Network.responseReceived',params:{requestId:'refresh',response:{url:'https://api-c.liepin.com/api/com.liepin.cresume.refresh-resume'}}}];},
  async cdp(method,args){if(method==='Network.enable')return {};return {body:JSON.stringify(args.requestId==='owner'?{data:{resId:fixture.wrongResume?'other-resume':'fixture-resume'}}:{flag:fixture.nativeFail?0:1,data:{}})};}
 };},
 async finish(){finished=true;}
};}
'''


@unittest.skipUnless(shutil.which("node"), "Worker tests require Node.js")
class WorkerTests(unittest.TestCase):
    def worker(self, fixture, dry=False):
        with tempfile.TemporaryDirectory() as temp:
            marker = Path(temp) / "click.json"
            inputs = {"binding": binding(), "dryRun": dry, "markerPath": str(marker), "day": "2026-10-28", "nowISO": NOW.isoformat(), "today": [2026, 10, 28], "nowSeconds": 32580, "browser": "cdp"}
            worker = Path(__file__).with_name("browser_worker.mjs").read_text(encoding="utf-8")
            code = "const input=" + json.dumps(inputs) + ";const fixture=" + json.dumps(fixture) + ";\n" + FAKE_BROWSER + worker + '\nconsole.log("TEST " + JSON.stringify({clicks,finished}));'
            run = subprocess.run([shutil.which("node"), "--input-type=module"], input=code, text=True, encoding="utf-8", capture_output=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(next(s for s in run.stdout.splitlines() if s.startswith("LIEPIN_RESULT ")).split(" ",1)[1])
            counts = json.loads(next(s for s in run.stdout.splitlines() if s.startswith("TEST ")).split(" ",1)[1])
            return result, counts, marker.exists()

    def test_preflight_stops_without_click(self):
        cases = [({"login":True},"needs_login"),({"wrongOwner":True},"identity_mismatch"),({"wrongResume":True},"identity_mismatch"),({"ambiguous":True},"binding_changed"),({"disabled":True},"binding_changed"),({"paid":True},"paid_required"),({"challenge":True},"challenge")]
        for fixture, expected in cases:
            with self.subTest(fixture=fixture):
                result, counts, marker = self.worker(fixture)
                self.assertEqual(result["status"], expected)
                self.assertEqual(counts["clicks"], 0)
                self.assertFalse(marker)

    def test_native_success_is_verified(self):
        result, counts, marker = self.worker({})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["evidence"], "native_api_flag_1")
        self.assertEqual(counts["clicks"], 1)
        self.assertTrue(marker)

    def test_image_success_surface(self):
        result, _, _ = self.worker({"surface":True,"noNative":True})
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["evidence"], "verified_success_surface")

    def test_old_success_notice_is_not_new_success(self):
        result, counts, marker = self.worker({"staleSuccess":True,"noNative":True})
        self.assertEqual(result["status"], "unverified")
        self.assertEqual(counts["clicks"], 1)
        self.assertTrue(marker)

    def test_native_failure_wins_over_visual_surface(self):
        result, _, _ = self.worker({"surface":True,"nativeFail":True})
        self.assertEqual(result["status"], "unverified")

    def test_identity_change_after_click(self):
        result, _, marker = self.worker({"wrongAfter":True})
        self.assertEqual(result["status"], "identity_mismatch")
        self.assertTrue(marker)

    def test_interrupted_click_retains_reservation(self):
        result, _, marker = self.worker({"clickThrows":True})
        self.assertEqual(result["status"], "unverified")
        self.assertTrue(marker)

    def test_user_control_stops_cleanup(self):
        result, counts, _ = self.worker({"clickThrows":True,"control":True})
        self.assertEqual(result["status"], "user_control")
        self.assertFalse(counts["finished"])

    def test_already_today_never_clicks(self):
        result, counts, marker = self.worker({"today":True})
        self.assertEqual(result["status"], "already_refreshed")
        self.assertEqual(counts["clicks"], 0)
        self.assertFalse(marker)

    def test_same_name_different_resume_cannot_confirm_today(self):
        result, _, _ = self.worker({"today":True,"wrongResume":True})
        self.assertEqual(result["status"], "identity_mismatch")

    def test_dry_run_is_observation_only(self):
        result, counts, marker = self.worker({}, dry=True)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(counts["clicks"], 0)
        self.assertFalse(marker)


class CDPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    commands = []
    closed = False

    def log_message(self, *args):
        pass

    def respond(self, value):
        body = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        self.respond({"id":"fixture","webSocketDebuggerUrl":f"ws://127.0.0.1:{self.server.server_port}/devtools/page/fixture"})

    def do_GET(self):
        if self.path.startswith("/json/close"):
            type(self).closed = True
            self.respond({"closed":True})
            return
        key = self.headers["Sec-WebSocket-Key"]
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        self.send_response(101)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.connection.settimeout(10)
        try:
            while True:
                header = self.rfile.read(2)
                if len(header) < 2 or header[0] & 15 == 8:
                    break
                length = header[1] & 127
                if length == 126:
                    length = struct.unpack("!H", self.rfile.read(2))[0]
                elif length == 127:
                    length = struct.unpack("!Q", self.rfile.read(8))[0]
                mask = self.rfile.read(4) if header[1] & 128 else None
                payload = self.rfile.read(length)
                if mask:
                    payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
                message = json.loads(payload)
                type(self).commands.append(message)
                result = {}
                if message["method"] == "Runtime.evaluate":
                    expression = message["params"]["expression"]
                    value = {"x":100,"y":200} if "Click target blocked" in expression else (42 if "=>42" in expression else True)
                    result = {"result":{"type":"object" if isinstance(value,dict) else "number", "value":value}}
                data = json.dumps({"id":message["id"],"result":result}).encode()
                prefix = bytes([129,len(data)]) if len(data)<126 else bytes([129,126])+struct.pack("!H",len(data))
                self.wfile.write(prefix+data)
                self.wfile.flush()
        except (OSError, ValueError, socket.timeout):
            pass


@unittest.skipUnless(shutil.which("node"), "CDP tests require Node.js")
class CDPTests(unittest.TestCase):
    def test_adapter_connects_clicks_and_closes_only_own_target(self):
        CDPHandler.commands = []
        CDPHandler.closed = False
        server = ThreadingHTTPServer(("127.0.0.1",0),CDPHandler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            adapter = Path(__file__).with_name("cdp_adapter.mjs").read_text(encoding="utf-8")
            code = f'const input={{cdpEndpoint:"http://127.0.0.1:{server.server_port}"}};\n' + adapter + '\nconst task=await taskSpace();const page=task.page();await page.goto("https://c.liepin.com/");console.log(await page.evaluate(()=>42));await page.click("loc=css:#refresh");await task.finish();'
            run = subprocess.run([shutil.which("node"),"--input-type=module"],input=code,text=True,encoding="utf-8",capture_output=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertIn("42",run.stdout)
            clicks = [command["params"] for command in CDPHandler.commands if command["method"]=="Input.dispatchMouseEvent"]
            self.assertEqual([click["type"] for click in clicks],["mousePressed","mouseReleased"])
            self.assertTrue(CDPHandler.closed)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
