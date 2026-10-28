#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import locale
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

LABEL = "local.liepin-resume-refresh"
TASK_NAME = "LiepinResumeRefresh"
CONFIRMED = {"success", "already_refreshed"}
OK = CONFIRMED | {"ready", "skipped_today", "skipped_running", "paused"}


def data_home() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "liepin-resume-refresh"
    return Path.home() / ".local/share/liepin-resume-refresh"


def private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, value) -> None:
    private_dir(path.parent)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    temporary.replace(path)


@contextlib.contextmanager
def exclusive(home: Path):
    private_dir(home)
    with (home / "run.lock").open("a+b") as stream:
        if sys.platform == "win32":
            import msvcrt
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def valid_time(value: str) -> str:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("时间格式应为 HH:MM，例如 09:03")
    return value


def validate_binding(binding: dict) -> dict:
    if not isinstance(binding, dict):
        raise ValueError("绑定应为 JSON 对象")
    required = ("resume_url", "identity_selector", "identity_sha256", "resume_id_sha256", "refresh_selector", "refresh_text")
    if any(not isinstance(binding.get(key), str) or not binding[key].strip() for key in required):
        raise ValueError("绑定缺少目标 URL、账号摘要或刷新控件")
    url = urlparse(binding["resume_url"])
    if url.scheme != "https" or url.netloc != "c.liepin.com" or url.username or "/vip" in url.path:
        raise ValueError("目标必须是现场观察到的猎聘候选人简历页 HTTPS URL")
    if any(not re.fullmatch(r"[a-f0-9]{64}", binding[key]) for key in ("identity_sha256", "resume_id_sha256")):
        raise ValueError("账号摘要应为 SHA-256 小写十六进制")
    if binding["refresh_text"] not in ("刷新", "刷新简历", "简历刷新", "立即刷新"):
        raise ValueError("刷新控件文字须为原生刷新操作")
    for key in ("identity_selector", "refresh_selector", "status_selector", "success_selector", "success_surface_selector", "blocked_selector"):
        value = binding.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip() or value.startswith(("@", "ref="))):
            raise ValueError("绑定必须使用经过观察的 CSS 选择器")
    if not (binding.get("status_selector") or binding.get("success_selector") or binding.get("success_surface_selector")):
        raise ValueError("至少配置刷新时间或明确成功提示")
    if binding.get("success_selector"):
        text = binding.get("success_text", "")
        if not isinstance(text, str) or "刷新" not in text or "成功" not in text:
            raise ValueError("成功提示应与页面实际的刷新成功文字一致")
    dismiss = binding.get("dismiss_selectors", [])
    if not isinstance(dismiss, list) or any(not isinstance(s, str) or not s.strip() for s in dismiss):
        raise ValueError("推广弹窗关闭选择器必须为列表")
    return binding


def binding_hash(binding: dict) -> str:
    return hashlib.sha256(json.dumps(binding, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def context_hash(config: dict) -> str:
    context = {key: config.get(key) for key in ("browser", "cdp_endpoint", "ego_space_id", "ego_page_label", "browser_executable", "node_executable")}
    context["binding"] = config.get("binding")
    return hashlib.sha256(json.dumps(context, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def config_for(home: Path) -> dict:
    config = read_json(home / "config.json")
    if not isinstance(config, dict) or config.get("schema_version") != 1:
        raise ValueError("请先执行 init 初始化配置")
    valid_time(config["daily_time"])
    return config


def browser_run(config: dict, home: Path, dry_run: bool, now: dt.datetime) -> dict:
    engine = config.get("browser", "ego")
    executable = config.get("node_executable") if engine == "cdp" else config.get("browser_executable")
    if not executable or not Path(executable).is_file():
        return {"status": "browser_missing", "attempted": False, "verified": False}
    binding = validate_binding(config["binding"])
    inputs = {
        "binding": binding, "dryRun": dry_run, "markerPath": str(home / "click.json"),
        "day": now.date().isoformat(), "nowISO": now.isoformat(),
        "today": [now.year, now.month, now.day],
        "nowSeconds": now.hour * 3600 + now.minute * 60 + now.second,
        "cdpEndpoint": config.get("cdp_endpoint"),
        "browser": engine, "spaceId": config.get("ego_space_id"), "pageLabel": config.get("ego_page_label", "p1"),
    }
    worker = Path(__file__).with_name("browser_worker.mjs").read_text(encoding="utf-8")
    adapter = Path(__file__).with_name("cdp_adapter.mjs").read_text(encoding="utf-8") if engine == "cdp" else ""
    code = "const input = " + json.dumps(inputs, ensure_ascii=False) + ";\n" + adapter + "\n" + worker
    command = [executable, "--input-type=module"] if engine == "cdp" else [executable, "nodejs"]
    try:
        completed = subprocess.run(command, input=code, text=True, encoding="utf-8", capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        return {"status": "browser_timeout", "attempted": False, "verified": False}
    lines = [line for line in (completed.stdout + "\n" + completed.stderr).splitlines() if line.startswith("LIEPIN_RESULT ")]
    if completed.returncode or len(lines) != 1:
        return {"status": "browser_error", "attempted": False, "verified": False}
    try:
        result = json.loads(lines[0].removeprefix("LIEPIN_RESULT "))
        if isinstance(result, dict) and isinstance(result.get("status"), str):
            return result
    except (ValueError, TypeError):
        pass
    return {"status": "browser_error", "attempted": False, "verified": False}


def notify(status: str) -> None:
    if sys.platform != "darwin":
        return
    messages = {
        "needs_login": "请重新登录候选人猎聘账号。",
        "identity_mismatch": "猎聘账号发生变化，请核对目标候选人。",
        "binding_changed": "猎聘页面发生变化，请重新检查刷新入口。",
        "unverified": "刷新点击结果不明确，请在猎聘页面核对；今天不会重复点击。",
        "paid_required": "当前入口要求付费，请检查免费刷新入口。",
        "challenge": "猎聘要求安全验证，请本人在网页处理。",
        "rate_limited": "猎聘提示刷新次数或操作频率受限。",
        "recovered": "猎聘简历刷新已恢复正常。",
    }
    message = messages.get(status, "猎聘简历刷新需要检查，请查看运行状态。")
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.run(["/usr/bin/osascript", "-e", f'display notification "{escaped}" with title "猎聘简历自动刷新"'], capture_output=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        pass


def record(home: Path, result: dict, state: dict, now: dt.datetime, config: dict, dry_run: bool) -> dict:
    result = {**result, "at": now.isoformat()}
    previous = state.get("last_result", {}).get("status")
    state["last_check" if dry_run else "last_result"] = result
    if result.get("verified") and result["status"] in CONFIRMED and (not dry_run or result["status"] == "already_refreshed"):
        state["last_confirmed_day"] = now.date().isoformat()
        state["verified_binding"] = binding_hash(config["binding"])
        state["verified_context"] = context_hash(config)
        state["last_success"] = result
    write_json(home / "state.json", state)
    events = home / "events.jsonl"
    lines = events.read_text(encoding="utf-8").splitlines()[-999:] if events.exists() else []
    lines.append(json.dumps(result, ensure_ascii=False))
    events.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(events, 0o600)
    if not dry_run and result["status"] != previous:
        if result["status"] not in OK:
            notify(result["status"])
        elif result["status"] in CONFIRMED and previous and previous not in OK:
            notify("recovered")
    return result


def run_once(home: Path, dry_run=False, scheduled=False, now=None) -> dict:
    now = now or dt.datetime.now().astimezone()
    config = config_for(home)
    state = read_json(home / "state.json", {})
    if scheduled and not config.get("enabled"):
        return {"status": "paused", "attempted": False, "verified": False}
    if not config.get("binding"):
        return record(home, {"status": "needs_setup", "attempted": False, "verified": False}, state, now, config, dry_run)
    marker = read_json(home / "click.json", {})
    if not dry_run and (marker.get("day") == now.date().isoformat() or state.get("last_confirmed_day") == now.date().isoformat()):
        return {"status": "skipped_today", "attempted": False, "verified": False, "at": now.isoformat()}
    result = browser_run(config, home, dry_run, now)
    marker = read_json(home / "click.json", {})
    if not dry_run and marker.get("day") == now.date().isoformat():
        result["attempted"] = True
        if result["status"] in ("browser_timeout", "browser_error"):
            result["status"] = "unverified"
    return record(home, result, state, now, config, dry_run)


def execute(command: list[str], check=True) -> subprocess.CompletedProcess:
    raw = subprocess.run(command, capture_output=True, timeout=30)
    def decode(value):
        if isinstance(value, str):
            return value
        if value.startswith((b'\xff\xfe', b'\xfe\xff')):
            return value.decode('utf-16')
        if b'\x00' in value[:80]:
            return value.decode('utf-16-le')
        return value.decode(locale.getpreferredencoding(False), errors='replace')
    completed = subprocess.CompletedProcess(command,raw.returncode,decode(raw.stdout),decode(raw.stderr))
    if check and completed.returncode:
        raise RuntimeError("本机调度器拒绝命令，请检查当前用户会话和权限")
    return completed


def owns_windows_task(xml: str, home: Path) -> bool:
    try:
        document = ET.fromstring(xml)
    except ET.ParseError:
        return False
    arguments = ' '.join(element.text or '' for element in document.iter() if element.tag.rsplit('}',1)[-1] == 'Arguments')
    expected = str(home / 'skill/scripts/refresh.py')
    return expected.replace('/','\\').casefold() in arguments.replace('/','\\').casefold()


def scheduler_plan(home: Path, time: str, platform: str | None = None) -> dict:
    platform = platform or sys.platform
    hour, minute = map(int, valid_time(time).split(":"))
    interpreter = str(Path(shutil.which("python3") or sys.executable).absolute())
    script = home / "skill/scripts/refresh.py"
    arguments = [interpreter, str(script), "--data-dir", str(home), "run", "--scheduled"]
    if platform == "darwin":
        return {"platform": platform, "plist": {
            "Label": LABEL, "ProgramArguments": arguments,
            "StartCalendarInterval": {"Hour": hour, "Minute": minute},
            "RunAtLoad": False, "ProcessType": "Background",
            "EnvironmentVariables": {"PATH": os.pathsep.join(dict.fromkeys([str(Path(interpreter).parent), str(Path(shutil.which("ego-browser") or "").parent), "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]))},
            "StandardOutPath": str(home / "scheduler.stdout.log"),
            "StandardErrorPath": str(home / "scheduler.stderr.log"),
        }}
    if platform == "win32":
        return {"platform": platform, "create": ["schtasks", "/Create", "/TN", TASK_NAME, "/TR", subprocess.list2cmdline(arguments), "/SC", "DAILY", "/ST", time, "/IT", "/F"]}
    raise ValueError("持久调度当前支持 macOS 和 Windows")


def schedule_status(home: Path) -> dict:
    if sys.platform == "darwin":
        target = f"gui/{os.getuid()}/{LABEL}"
        result = execute(["launchctl", "print", target], check=False)
        file = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
        owned = False
        if file.exists():
            value = plistlib.loads(file.read_bytes())
            owned = str(home / "skill/scripts/refresh.py") in value.get("ProgramArguments", [])
        return {"registered": result.returncode == 0 and owned, "platform": "macOS", "owned": owned}
    if sys.platform == "win32":
        result = execute(["schtasks", "/Query", "/TN", TASK_NAME, "/XML"], check=False)
        owned = result.returncode == 0 and owns_windows_task(result.stdout, home)
        return {"registered": owned, "platform": "Windows", "owned": owned}
    return {"registered": False, "platform": sys.platform}


def require_verified(home: Path, config: dict) -> None:
    state = read_json(home / "state.json", {})
    if not config.get("binding") or state.get("verified_binding") != binding_hash(config["binding"]) or state.get("verified_context") != context_hash(config):
        raise ValueError("当前账号绑定尚未经过真实刷新验证，请先执行 run")


def prepare_runtime(home: Path) -> Path:
    source = Path(__file__).resolve().parent.parent
    destination = home / "skill"
    if source != destination.resolve():
        shutil.copytree(source, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "node_modules", "dist", "work", "outputs"))
    return destination / "scripts/refresh.py"


def record_agent_schedule(home: Path, config: dict, job_id: str, time: str) -> dict:
    require_verified(home, config)
    if not job_id.strip() or len(job_id) > 200 or "\n" in job_id:
        raise ValueError("需要宿主定时工具返回的真实任务 ID")
    if schedule_status(home).get("registered"):
        raise ValueError("已有本机定时任务；切换前先删除原任务，避免同时注册两个调度器")
    script = prepare_runtime(home)
    config.update(enabled=True, daily_time=valid_time(time), scheduler_mode="agent", agent_job_id=job_id)
    write_json(home / "config.json", config)
    return {"saved": True, "enabled": True, "scheduler_mode": "agent", "job_id": job_id, "daily_time": time, "script": str(script), "host_status": "verify_with_host_tool"}


def schedule_install(home: Path, config: dict, time: str) -> dict:
    require_verified(home, config)
    if config.get("scheduler_mode") == "agent" and config.get("agent_job_id"):
        raise ValueError("先通过宿主定时工具删除 AI 任务，再执行 agent-schedule clear，然后切换本机调度")
    time = valid_time(time)
    plan = scheduler_plan(home, time)
    config["enabled"] = False
    write_json(home / "config.json", config)
    prepare_runtime(home)
    if sys.platform == "darwin":
        file = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
        private_dir(file.parent)
        if file.exists():
            existing = plistlib.loads(file.read_bytes())
            if str(home / "skill/scripts/refresh.py") not in existing.get("ProgramArguments", []):
                raise ValueError("同名调度任务属于另一配置目录，不能覆盖")
        execute(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], check=False)
        file.write_bytes(plistlib.dumps(plan["plist"]))
        os.chmod(file, 0o600)
        execute(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(file)])
    else:
        existing = execute(["schtasks", "/Query", "/TN", TASK_NAME, "/XML"], check=False)
        if existing.returncode == 0 and not owns_windows_task(existing.stdout, home):
            raise ValueError("同名 Windows 任务属于另一配置，不能覆盖")
        execute(plan["create"])
    actual = schedule_status(home)
    if not actual["registered"]:
        raise RuntimeError("调度器注册结果未通过回读核验，任务保持暂停")
    config.update(enabled=True, daily_time=time, scheduler_mode="local")
    write_json(home / "config.json", config)
    return {**actual, "enabled": True, "daily_time": time, "timezone": str(dt.datetime.now().astimezone().tzinfo)}


def schedule_remove(home: Path, config: dict) -> dict:
    config["enabled"] = False
    write_json(home / "config.json", config)
    actual = schedule_status(home)
    if not actual.get("owned"):
        return {"registered": False, "enabled": False, "removed": False}
    if sys.platform == "darwin":
        execute(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], check=False)
        (Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")).unlink(missing_ok=True)
    else:
        execute(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
    if schedule_status(home)["registered"]:
        raise RuntimeError("调度任务仍然存在，请检查调度器")
    return {"registered": False, "enabled": False, "removed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="猎聘简历自动刷新与定时管理")
    parser.add_argument("--data-dir", type=Path, default=data_home())
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--time", default="09:03")
    configure = commands.add_parser("configure")
    configure.add_argument("--binding-file", type=Path, required=True)
    configure.add_argument("--browser", choices=("ego", "cdp"), default="ego")
    configure.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    configure.add_argument("--space-id", type=int)
    configure.add_argument("--page-label", default="p1")
    run = commands.add_parser("run")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--scheduled", action="store_true")
    commands.add_parser("status")
    commands.add_parser("pause")
    commands.add_parser("prepare")
    agent_schedule = commands.add_parser("agent-schedule")
    agent_actions = agent_schedule.add_subparsers(dest="agent_action", required=True)
    agent_record = agent_actions.add_parser("record")
    agent_record.add_argument("--job-id", required=True)
    agent_record.add_argument("--time", default="09:03")
    agent_actions.add_parser("status")
    agent_actions.add_parser("clear")
    schedule = commands.add_parser("schedule")
    actions = schedule.add_subparsers(dest="action", required=True)
    install = actions.add_parser("install")
    install.add_argument("--time")
    actions.add_parser("status")
    actions.add_parser("remove")
    args = parser.parse_args()
    home = args.data_dir.expanduser().absolute()
    try:
        with exclusive(home):
            if args.command == "init":
                if (home / "config.json").exists():
                    config = config_for(home)
                else:
                    config = {"schema_version": 1, "enabled": False, "daily_time": valid_time(args.time), "browser": "ego", "browser_executable": shutil.which("ego-browser"), "binding": None}
                    write_json(home / "config.json", config)
                result = {"initialized": True, "enabled": config["enabled"], "daily_time": config["daily_time"], "needs_setup": not bool(config["binding"])}
            elif args.command == "run":
                result = run_once(home, args.dry_run, args.scheduled)
            else:
                config = config_for(home)
                if args.command == "configure":
                    binding = validate_binding(read_json(args.binding_file))
                    state = read_json(home / "state.json", {})
                    state.pop("verified_binding", None)
                    state.pop("verified_context", None)
                    write_json(home / "state.json", state)
                    config.update(binding=binding, enabled=False, browser_executable=shutil.which("ego-browser"))
                    if args.browser == "cdp":
                        endpoint = urlparse(args.cdp_endpoint)
                        if endpoint.scheme != "http" or endpoint.hostname not in ("127.0.0.1", "localhost", "::1") or not endpoint.port or endpoint.username or endpoint.path not in ("", "/"):
                            raise ValueError("CDP 仅支持本机回环 HTTP 端口")
                        if not shutil.which("node"):
                            raise ValueError("CDP 适配器需要 Node.js 22 或以上")
                    elif args.space_id is None or args.space_id <= 0:
                        raise ValueError("Ego 模式需要首次登录的任务空间 --space-id，保留该空间的登录态")
                    config.update(browser=args.browser, cdp_endpoint=args.cdp_endpoint, node_executable=shutil.which("node"))
                    config.update(ego_space_id=args.space_id, ego_page_label=args.page_label)
                    write_json(home / "config.json", config)
                    result = {"configured": True, "enabled": False, "requires_live_check": True}
                elif args.command == "status":
                    result = {"enabled": config["enabled"], "daily_time": config["daily_time"], "configured": bool(config["binding"]), "scheduler_mode": config.get("scheduler_mode", "local"), "agent_job_id": config.get("agent_job_id"), **read_json(home / "state.json", {}), "click": read_json(home / "click.json", {})}
                elif args.command == "prepare":
                    result = {"prepared": True, "script": str(prepare_runtime(home)), "enabled": config["enabled"]}
                elif args.command == "agent-schedule":
                    if args.agent_action == "record":
                        result = record_agent_schedule(home, config, args.job_id, args.time)
                    elif args.agent_action == "clear":
                        config.update(enabled=False, scheduler_mode="none")
                        config.pop("agent_job_id", None)
                        write_json(home / "config.json", config)
                        result = {"enabled": False, "saved": False, "host_status": "delete_with_host_tool"}
                    else:
                        result = {"enabled": config["enabled"], "job_id": config.get("agent_job_id"), "daily_time": config["daily_time"], "host_status": "read_with_host_tool"}
                elif args.command == "pause":
                    config["enabled"] = False
                    write_json(home / "config.json", config)
                    result = {"enabled": False}
                elif args.action == "install":
                    result = schedule_install(home, config, args.time or config["daily_time"])
                elif args.action == "remove":
                    result = schedule_remove(home, config)
                else:
                    result = {**schedule_status(home), "enabled": config["enabled"], "daily_time": config["daily_time"]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status", "ready") in OK else 2
    except (BlockingIOError, PermissionError):
        print(json.dumps({"status": "skipped_running", "message": "任务正在运行，或无法获得私有目录锁"}, ensure_ascii=False))
        return 2
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "error", "message": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
