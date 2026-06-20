#!/usr/bin/env python3
"""BitMod Self-Healing Overnight Test Runner.

Wraps the test batches with a supervisor that:
  1. Monitors all services (Ollama, Gateway, Chat) continuously
  2. Detects failures: service down, error rate spikes, crashes, timeouts
  3. Diagnoses the root cause from error patterns + logs
  4. Fixes the issue: restarts the broken service(s)
  5. Resumes testing from the last successful batch

The entire loop runs indefinitely — after all 12 batches complete, it cycles
back with fresh random seeds to keep hammering the system. Ctrl+C to stop.

Usage:
    python -u tests/self_healing_runner.py
    python -u tests/self_healing_runner.py --cycles 3          # stop after 3 full cycles
    python -u tests/self_healing_runner.py --start-batch 5     # resume mid-cycle
    python -u tests/self_healing_runner.py --error-threshold 5 # tolerate 5 consecutive errors
"""

import argparse
import asyncio
import json
import os
import random
import signal
import socket
import statistics
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    print("ERROR: httpx required. pip install httpx")
    sys.exit(1)

try:
    import anthropic
    HAS_CLAUDE = True
except ImportError:
    HAS_CLAUDE = False

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "tests" / "overnight_results"
INCIDENT_LOG = RESULTS_DIR / "incidents.jsonl"
STATE_FILE = RESULTS_DIR / "runner_state.json"

PYTHON = sys.executable
UVICORN = [PYTHON, "-m", "uvicorn"]

CHAT_PORT = 8001
GATEWAY_PORT = 8000
OLLAMA_PORT = 11434

CHAT_MODULE = "services.chat.app.main:app"
GATEWAY_MODULE = "services.gateway.app.main:app"

ENV_BASE = {
    "PYTHONPATH": str(PROJECT_ROOT / "core"),
    "BITMOD_LLM_PRIMARY": "ollama",
    "BITMOD_LLM_MODEL": "llama3.2",
    "CORS_ORIGINS": "https://test.bitmod.io,https://bitmod.io",
    "PATH": os.environ.get("PATH", ""),
    "HOME": os.environ.get("HOME", ""),
    "LANG": os.environ.get("LANG", "en_US.UTF-8"),
}

REQUEST_TIMEOUT = 120.0
HEALTH_CHECK_TIMEOUT = 10.0
MAX_CONSECUTIVE_ERRORS = 10
SERVICE_RESTART_WAIT = 5
MAX_RESTART_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# Import batch logic from overnight_runner
# ---------------------------------------------------------------------------

sys.path.insert(0, str(PROJECT_ROOT / "tests"))
from overnight_runner import (
    FILTER_SETS, BatchReport, Result,
    batch_1_chat_basics, batch_2_cache_replay, batch_3_filter_variations,
    batch_4_composable, batch_5_search, batch_6_fuzzy, batch_7_stats,
    batch_8_streaming, batch_9_invalidation, batch_10_throughput,
    batch_11_scale, batch_12_final_stats,
    compute_report, save_report, print_batch_summary, make_prompt,
)

# ---------------------------------------------------------------------------
# Incident tracking
# ---------------------------------------------------------------------------

@dataclass
class Incident:
    timestamp: str
    batch: int
    cycle: int
    error_type: str          # service_down, error_spike, crash, timeout
    service: str             # ollama, chat, gateway, runner
    diagnosis: str           # human-readable root cause
    action_taken: str        # what the healer did
    resolved: bool = False
    resolution_time_s: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def log_incident(incident: Incident):
    """Append incident to JSONL log."""
    INCIDENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(INCIDENT_LOG, "a") as f:
        f.write(json.dumps(incident.to_dict()) + "\n")
    tag = "RESOLVED" if incident.resolved else "UNRESOLVED"
    print(f"\n  [{tag}] {incident.error_type} in {incident.service}: {incident.diagnosis}")
    print(f"  Action: {incident.action_taken}")
    if incident.resolved:
        print(f"  Fixed in {incident.resolution_time_s:.1f}s")


# ---------------------------------------------------------------------------
# State persistence (resume across crashes of the runner itself)
# ---------------------------------------------------------------------------

def save_state(cycle: int, batch: int, seed: int):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({
        "cycle": cycle, "batch": batch, "seed": seed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))


def load_state() -> dict | None:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Service management
# ---------------------------------------------------------------------------

def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_port(port: int):
    """Kill whatever is listening on a port."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = result.stdout.strip().split("\n")
        for pid in pids:
            if pid.strip():
                try:
                    os.kill(int(pid.strip()), signal.SIGKILL)
                except (ProcessLookupError, ValueError):
                    pass
    except Exception:
        pass


def start_service(name: str, module: str, port: int, log_path: Path) -> subprocess.Popen:
    """Start a uvicorn service as a subprocess."""
    kill_port(port)
    time.sleep(1)

    env = {**os.environ, **ENV_BASE}
    cmd = UVICORN + [module, "--host", "0.0.0.0", "--port", str(port)]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(log_path, "a")
    log_file.write(f"\n--- {name} starting at {datetime.now().isoformat()} ---\n")
    log_file.flush()

    proc = subprocess.Popen(
        cmd, env=env, cwd=str(PROJECT_ROOT),
        stdout=log_file, stderr=subprocess.STDOUT,
    )
    print(f"  Started {name} (PID {proc.pid}) on port {port}")
    return proc


async def health_check(url: str, timeout: float = HEALTH_CHECK_TIMEOUT) -> tuple[bool, str]:
    """Check if a service is healthy. Returns (ok, detail)."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{url}/health", timeout=timeout)
            if resp.status_code == 200:
                return True, "ok"
            return False, f"status {resp.status_code}: {resp.text[:100]}"
    except httpx.ConnectError:
        return False, "connection refused"
    except httpx.TimeoutException:
        return False, "timeout"
    except Exception as e:
        return False, str(e)[:100]


async def check_ollama() -> tuple[bool, str]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://localhost:{OLLAMA_PORT}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                has_model = any("llama3.2" in m.get("name", "") for m in models)
                if has_model:
                    return True, "ok"
                return False, "llama3.2 model not found"
            return False, f"status {resp.status_code}"
    except Exception as e:
        return False, str(e)[:100]


# ---------------------------------------------------------------------------
# Diagnosis engine
# ---------------------------------------------------------------------------

class Diagnostician:
    """Analyzes failures and determines root cause + fix action."""

    @staticmethod
    async def diagnose(
        error: Exception | None,
        batch_num: int,
        recent_results: list[Result],
        services_status: dict[str, tuple[bool, str]],
    ) -> tuple[str, str, str]:
        """
        Returns (error_type, service, diagnosis).
        """
        # Check which services are down
        down_services = {k: v[1] for k, v in services_status.items() if not v[0]}

        if down_services:
            if "ollama" in down_services:
                return "service_down", "ollama", f"Ollama not responding: {down_services['ollama']}"
            if "chat" in down_services:
                return "service_down", "chat", f"Chat service down: {down_services['chat']}"
            if "gateway" in down_services:
                return "service_down", "gateway", f"Gateway down: {down_services['gateway']}"

        # Check error patterns in recent results
        if recent_results:
            error_count = sum(1 for r in recent_results[-20:] if r.status != 200)
            timeout_count = sum(1 for r in recent_results[-20:] if r.error and "timeout" in r.error.lower())
            conn_refused = sum(1 for r in recent_results[-20:] if r.error and "connect" in r.error.lower())

            if conn_refused > 3:
                return "service_down", "gateway", f"{conn_refused}/20 connection refused errors"
            if timeout_count > 5:
                return "timeout", "ollama", f"{timeout_count}/20 timeouts — Ollama likely overloaded"
            if error_count > 10:
                # Check the actual error messages
                errors = [r.error for r in recent_results[-20:] if r.error]
                sample = errors[0] if errors else "unknown"
                if "500" in str([r.status for r in recent_results[-20:]]):
                    return "error_spike", "chat", f"{error_count}/20 errors, sample: {sample}"
                return "error_spike", "gateway", f"{error_count}/20 errors, sample: {sample}"

        # If we got an exception
        if error:
            err_str = str(error).lower()
            if "connection" in err_str or "refused" in err_str:
                return "service_down", "gateway", f"Connection error: {error}"
            if "timeout" in err_str:
                return "timeout", "ollama", f"Timeout: {error}"
            return "crash", "runner", f"Unexpected error: {error}"

        return "unknown", "runner", "Unknown failure — no clear signal"


# ---------------------------------------------------------------------------
# Code fixer — reads tracebacks, identifies bugs, patches source
# ---------------------------------------------------------------------------

class CodeFixer:
    """Uses Claude API to read tracebacks, identify the bug, and generate a fix."""

    # Map service names to their source directories for context
    SERVICE_PATHS = {
        "chat": "services/chat/app/main.py",
        "gateway": "services/gateway/app/main.py",
    }
    CORE_PATHS = [
        "core/bitmod/cache_engine.py",
        "core/bitmod/pipeline.py",
        "core/bitmod/interfaces/database.py",
        "core/bitmod/adapters/db_sqlite.py",
        "core/bitmod/security.py",
        "core/bitmod/schemas.py",
        "core/bitmod/config.py",
    ]

    def __init__(self):
        self.fixes_applied: list[dict] = []
        self.client = anthropic.Anthropic() if HAS_CLAUDE else None

    def _read_file(self, rel_path: str) -> str | None:
        full = PROJECT_ROOT / rel_path
        if full.exists():
            try:
                return full.read_text()
            except Exception:
                return None
        return None

    def _write_file(self, rel_path: str, content: str):
        full = PROJECT_ROOT / rel_path
        full.write_text(content)

    def _tail_log(self, log_path: Path, lines: int = 100) -> str:
        if not log_path.exists():
            return ""
        try:
            all_lines = log_path.read_text().splitlines()
            return "\n".join(all_lines[-lines:])
        except Exception:
            return ""

    def _extract_traceback(self, log_text: str) -> str:
        """Pull the most recent traceback from log output."""
        lines = log_text.splitlines()
        tb_lines: list[str] = []
        in_tb = False
        for line in lines:
            if "Traceback (most recent call last)" in line:
                tb_lines = [line]
                in_tb = True
            elif in_tb:
                tb_lines.append(line)
                if line and not line.startswith(" ") and "Error" in line:
                    in_tb = False
        return "\n".join(tb_lines[-50:]) if tb_lines else ""

    def _extract_file_from_traceback(self, tb: str) -> str | None:
        """Get the source file path from the last frame in a traceback."""
        import re
        # Match: File "/path/to/file.py", line N
        matches = re.findall(r'File "([^"]+)", line (\d+)', tb)
        # Return the last file that's in our project
        project_str = str(PROJECT_ROOT)
        for fpath, lineno in reversed(matches):
            if project_str in fpath:
                # Convert absolute to relative
                return fpath.replace(project_str + "/", "")
        return None

    async def try_fix(
        self,
        service: str,
        error_text: str,
        log_path: Path | None = None,
    ) -> tuple[bool, str]:
        """
        Attempt to fix a code bug using Claude.

        Returns (fixed, description_of_fix).
        """
        if not HAS_CLAUDE or not self.client:
            return False, "Claude API not available (pip install anthropic)"

        # Gather context
        tb = ""
        if log_path:
            log_text = self._tail_log(log_path, 150)
            tb = self._extract_traceback(log_text)

        if not tb and error_text:
            tb = error_text

        if not tb:
            return False, "No traceback to analyze"

        # Find the file to fix
        target_file = self._extract_file_from_traceback(tb)
        if not target_file:
            target_file = self.SERVICE_PATHS.get(service)
        if not target_file:
            return False, f"Cannot identify source file for {service}"

        target_content = self._read_file(target_file)
        if not target_content:
            return False, f"Cannot read {target_file}"

        # Gather related files for context
        related_context = ""
        for rp in self.CORE_PATHS:
            content = self._read_file(rp)
            if content:
                related_context += f"\n\n--- {rp} ---\n{content[:3000]}"

        print(f"  CODE-FIX: Analyzing {target_file} with Claude...")

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": f"""You are a Python debugging assistant. A service crashed with this traceback:

```
{tb}
```

The failing source file is `{target_file}`:
```python
{target_content}
```

Related imports/modules for context (truncated):
{related_context[:6000]}

Your task:
1. Identify the exact bug from the traceback
2. Return ONLY the fixed version of `{target_file}` — the complete file content
3. Make the MINIMUM change needed to fix the bug. Do not refactor, add features, or change anything unrelated.

Return your answer as:
DIAGNOSIS: <one line explanation of the bug>
FIX_START
<complete file content>
FIX_END"""
                }],
            )

            reply = response.content[0].text

            # Parse the response
            diagnosis = ""
            fixed_content = ""

            if "DIAGNOSIS:" in reply:
                diagnosis = reply.split("DIAGNOSIS:")[1].split("\n")[0].strip()

            if "FIX_START" in reply and "FIX_END" in reply:
                fixed_content = reply.split("FIX_START")[1].split("FIX_END")[0].strip()
                # Strip markdown code fences if present
                if fixed_content.startswith("```"):
                    lines = fixed_content.splitlines()
                    # Remove first and last ``` lines
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    fixed_content = "\n".join(lines)

            if not fixed_content:
                return False, f"Claude could not generate a fix. Diagnosis: {diagnosis}"

            # Validate the fix isn't empty or drastically different
            orig_lines = len(target_content.splitlines())
            fix_lines = len(fixed_content.splitlines())
            if fix_lines < orig_lines * 0.5:
                return False, f"Fix too destructive ({fix_lines} vs {orig_lines} lines) — skipping"
            if fix_lines > orig_lines * 2:
                return False, f"Fix too large ({fix_lines} vs {orig_lines} lines) — skipping"

            # Backup original
            backup_path = RESULTS_DIR / "backups" / f"{target_file.replace('/', '_')}.{int(time.time())}.bak"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(target_content)

            # Apply fix
            self._write_file(target_file, fixed_content)

            fix_record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "service": service,
                "file": target_file,
                "diagnosis": diagnosis,
                "backup": str(backup_path),
                "original_lines": orig_lines,
                "fixed_lines": fix_lines,
            }
            self.fixes_applied.append(fix_record)

            # Save fix log
            fixes_log = RESULTS_DIR / "code_fixes.jsonl"
            with open(fixes_log, "a") as f:
                f.write(json.dumps(fix_record) + "\n")

            print(f"  CODE-FIX: {diagnosis}")
            print(f"  CODE-FIX: Patched {target_file} ({orig_lines}→{fix_lines} lines)")
            print(f"  CODE-FIX: Backup at {backup_path.name}")

            return True, f"Fixed {target_file}: {diagnosis}"

        except Exception as e:
            return False, f"Claude API error: {e}"


# ---------------------------------------------------------------------------
# Healer — takes action to fix problems
# ---------------------------------------------------------------------------

class Healer:
    """Restarts services, and if that fails, uses Claude to fix code bugs."""

    def __init__(self):
        self.chat_proc: subprocess.Popen | None = None
        self.gateway_proc: subprocess.Popen | None = None
        self.restart_counts: dict[str, int] = {"ollama": 0, "chat": 0, "gateway": 0}
        self.code_fixer = CodeFixer()

    async def heal(self, service: str, error_type: str, error_detail: str = "") -> tuple[bool, str]:
        """
        Attempt to fix the service. Strategy:
          1. First try: simple restart
          2. If restart fails or error is 500/crash: use Claude to fix the code, then restart
          3. If code fix fails: give up

        Returns (success, action_description).
        """
        if self.restart_counts.get(service, 0) >= MAX_RESTART_ATTEMPTS:
            return False, f"Exceeded {MAX_RESTART_ATTEMPTS} restart attempts for {service}"

        self.restart_counts[service] = self.restart_counts.get(service, 0) + 1
        attempt = self.restart_counts[service]

        # Step 1: Try simple restart first
        if service == "ollama":
            ok, msg = await self._heal_ollama(attempt)
        elif service == "chat":
            ok, msg = await self._heal_chat(attempt)
        elif service == "gateway":
            ok, msg = await self._heal_gateway(attempt)
        else:
            return False, f"No heal strategy for {service}"

        if ok:
            return True, msg

        # Step 2: Restart didn't work — try code fix
        if service in ("chat", "gateway") and error_type in ("error_spike", "crash", "service_down"):
            print(f"\n  Simple restart failed for {service}. Attempting code fix...")
            log_path = RESULTS_DIR / f"{service}_service.log"
            fixed, fix_msg = await self.code_fixer.try_fix(service, error_detail, log_path)
            if fixed:
                # Restart with fixed code
                if service == "chat":
                    ok2, msg2 = await self._heal_chat(attempt)
                else:
                    ok2, msg2 = await self._heal_gateway(attempt)
                if ok2:
                    self.restart_counts[service] = 0
                    return True, f"{fix_msg} + {msg2}"
                return False, f"Code fixed but service still won't start: {msg2}"
            return False, f"Restart failed ({msg}) and code fix failed ({fix_msg})"

        return False, msg

    async def _heal_ollama(self, attempt: int) -> tuple[bool, str]:
        """Ollama is an external service — we can try restarting it."""
        action = f"Restarting Ollama (attempt {attempt})"
        print(f"  HEAL: {action}")

        try:
            subprocess.run(["pkill", "-f", "ollama serve"], timeout=5, capture_output=True)
            time.sleep(2)
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            time.sleep(5)

            ok, detail = await check_ollama()
            if ok:
                self.restart_counts["ollama"] = 0  # reset on success
                return True, f"{action} — OK"
            return False, f"{action} — still unhealthy: {detail}"
        except FileNotFoundError:
            # Ollama might be running as a macOS app, not CLI
            # Try the app approach
            try:
                subprocess.run(["open", "-a", "Ollama"], timeout=10, capture_output=True)
                time.sleep(8)
                ok, detail = await check_ollama()
                if ok:
                    self.restart_counts["ollama"] = 0
                    return True, f"Opened Ollama.app — OK"
                return False, f"Opened Ollama.app but still unhealthy: {detail}"
            except Exception as e:
                return False, f"Cannot restart Ollama: {e}"

    async def _heal_chat(self, attempt: int) -> tuple[bool, str]:
        action = f"Restarting chat service (attempt {attempt})"
        print(f"  HEAL: {action}")

        if self.chat_proc:
            try:
                self.chat_proc.kill()
                self.chat_proc.wait(timeout=5)
            except Exception:
                pass

        log_path = RESULTS_DIR / "chat_service.log"
        self.chat_proc = start_service("chat", CHAT_MODULE, CHAT_PORT, log_path)
        time.sleep(SERVICE_RESTART_WAIT)

        ok, detail = await health_check(f"http://localhost:{CHAT_PORT}")
        if ok:
            self.restart_counts["chat"] = 0
            return True, f"{action} — OK"
        return False, f"{action} — still unhealthy: {detail}"

    async def _heal_gateway(self, attempt: int) -> tuple[bool, str]:
        action = f"Restarting gateway (attempt {attempt})"
        print(f"  HEAL: {action}")

        if self.gateway_proc:
            try:
                self.gateway_proc.kill()
                self.gateway_proc.wait(timeout=5)
            except Exception:
                pass

        log_path = RESULTS_DIR / "gateway_service.log"
        self.gateway_proc = start_service("gateway", GATEWAY_MODULE, GATEWAY_PORT, log_path)
        time.sleep(SERVICE_RESTART_WAIT)

        ok, detail = await health_check(f"http://localhost:{GATEWAY_PORT}")
        if ok:
            self.restart_counts["gateway"] = 0
            return True, f"{action} — OK"
        return False, f"{action} — still unhealthy: {detail}"

    async def ensure_all_healthy(self) -> dict[str, tuple[bool, str]]:
        """Check all services, heal any that are down. Returns final status."""
        status = {}
        status["ollama"] = await check_ollama()
        status["chat"] = await health_check(f"http://localhost:{CHAT_PORT}")
        status["gateway"] = await health_check(f"http://localhost:{GATEWAY_PORT}")

        for svc, (ok, detail) in status.items():
            if not ok:
                print(f"\n  {svc} is down: {detail}")
                healed, action = await self.heal(svc, "service_down", detail)
                if healed:
                    status[svc] = (True, "healed")
                else:
                    print(f"  FAILED to heal {svc}: {action}")

        return status

    async def start_all(self):
        """Start chat + gateway if not already running."""
        chat_ok, _ = await health_check(f"http://localhost:{CHAT_PORT}")
        if not chat_ok:
            log_path = RESULTS_DIR / "chat_service.log"
            self.chat_proc = start_service("chat", CHAT_MODULE, CHAT_PORT, log_path)
            time.sleep(SERVICE_RESTART_WAIT)

        gw_ok, _ = await health_check(f"http://localhost:{GATEWAY_PORT}")
        if not gw_ok:
            log_path = RESULTS_DIR / "gateway_service.log"
            self.gateway_proc = start_service("gateway", GATEWAY_MODULE, GATEWAY_PORT, log_path)
            time.sleep(SERVICE_RESTART_WAIT)

    def cleanup(self):
        """Kill managed processes on shutdown."""
        for proc in [self.chat_proc, self.gateway_proc]:
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Self-healing batch executor
# ---------------------------------------------------------------------------

async def run_batch_with_healing(
    batch_num: int,
    cycle: int,
    client: httpx.AsyncClient,
    api_url: str,
    rng: random.Random,
    healer: Healer,
    batch1_sent: list,
    batch1_prompts: list,
    error_threshold: int,
) -> tuple[BatchReport | None, list, list]:
    """
    Run a single batch with self-healing. On failure:
      1. Diagnose the problem
      2. Fix it (restart services)
      3. Retry the batch (up to 3 times)

    Returns (report, updated_batch1_sent, updated_batch1_prompts)
    """
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"\n  Retry {attempt}/{max_retries} for batch {batch_num}")

        # Pre-flight health check
        status = await healer.ensure_all_healthy()
        all_up = all(ok for ok, _ in status.values())
        if not all_up:
            down = [k for k, (ok, _) in status.items() if not ok]
            incident = Incident(
                timestamp=datetime.now(timezone.utc).isoformat(),
                batch=batch_num, cycle=cycle,
                error_type="service_down", service=",".join(down),
                diagnosis=f"Services still down after healing: {down}",
                action_taken="Waiting 30s before retry",
                resolved=False,
            )
            log_incident(incident)
            await asyncio.sleep(30)
            continue

        try:
            report = None

            if batch_num == 1:
                report, batch1_sent = await batch_1_chat_basics(client, api_url, rng)
                batch1_prompts = [p for p, _ in batch1_sent]
            elif batch_num == 2:
                if not batch1_sent:
                    print("  Generating batch 1 data for replay...")
                    batch1_sent = [(make_prompt(rng), rng.choice(FILTER_SETS[:3])) for _ in range(200)]
                    batch1_prompts = [p for p, _ in batch1_sent]
                report = await batch_2_cache_replay(client, api_url, batch1_sent)
            elif batch_num == 3:
                if not batch1_prompts:
                    batch1_prompts = [make_prompt(rng) for _ in range(50)]
                report = await batch_3_filter_variations(client, api_url, rng, batch1_prompts)
            elif batch_num == 4:
                report = await batch_4_composable(client, api_url, rng)
            elif batch_num == 5:
                report = await batch_5_search(client, api_url, rng)
            elif batch_num == 6:
                if not batch1_prompts:
                    batch1_prompts = [make_prompt(rng) for _ in range(50)]
                report = await batch_6_fuzzy(client, api_url, rng, batch1_prompts)
            elif batch_num == 7:
                report = await batch_7_stats(client, api_url)
            elif batch_num == 8:
                report = await batch_8_streaming(client, api_url, rng)
            elif batch_num == 9:
                report = await batch_9_invalidation(client, api_url, rng)
            elif batch_num == 10:
                report = await batch_10_throughput(client, api_url, rng)
            elif batch_num == 11:
                report = await batch_11_scale(client, api_url, rng)
            elif batch_num == 12:
                report = await batch_12_final_stats(client, api_url)

            if report is None:
                return None, batch1_sent, batch1_prompts

            # Check error rate within the batch
            if report.errors > 0:
                error_rate = report.errors / max(report.total, 1)
                if error_rate > 0.5:
                    # More than half failed — diagnose and retry
                    status = await healer.ensure_all_healthy()
                    error_type, service, diagnosis = await Diagnostician.diagnose(
                        None, batch_num, report.results, status,
                    )
                    # Collect error samples for the code fixer
                    error_samples = "\n".join(
                        r.error for r in report.results if r.error
                    )[:2000]
                    start_heal = time.time()
                    healed, action = await healer.heal(service, error_type, error_samples)
                    heal_time = time.time() - start_heal

                    incident = Incident(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        batch=batch_num, cycle=cycle,
                        error_type=error_type, service=service,
                        diagnosis=f"{diagnosis} (error_rate={error_rate:.0%})",
                        action_taken=action,
                        resolved=healed,
                        resolution_time_s=heal_time,
                    )
                    log_incident(incident)

                    if healed and attempt < max_retries:
                        continue  # retry the batch
                    # If not healed or last attempt, return partial results
                    print(f"  Returning partial results ({report.successes}/{report.total} OK)")

            return report, batch1_sent, batch1_prompts

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"\n  EXCEPTION in batch {batch_num}: {e}")
            traceback.print_exc()

            # Diagnose
            status = await healer.ensure_all_healthy()
            error_type, service, diagnosis = await Diagnostician.diagnose(
                e, batch_num, [], status,
            )
            start_heal = time.time()
            healed, action = await healer.heal(service, error_type, str(e))
            heal_time = time.time() - start_heal

            incident = Incident(
                timestamp=datetime.now(timezone.utc).isoformat(),
                batch=batch_num, cycle=cycle,
                error_type=error_type, service=service,
                diagnosis=diagnosis,
                action_taken=action,
                resolved=healed,
                resolution_time_s=heal_time,
            )
            log_incident(incident)

            if not healed or attempt == max_retries:
                print(f"  Skipping batch {batch_num} after {attempt} attempts")
                return None, batch1_sent, batch1_prompts

            await asyncio.sleep(5)

    return None, batch1_sent, batch1_prompts


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def main(
    api_url: str,
    start_batch: int,
    max_cycles: int,
    error_threshold: int,
    timeout: float,
):
    import overnight_runner
    overnight_runner.TIMEOUT = timeout

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  BitMod Self-Healing Overnight Runner")
    print("=" * 60)
    print(f"  API:             {api_url}")
    print(f"  Results:         {RESULTS_DIR}")
    print(f"  Max cycles:      {max_cycles if max_cycles > 0 else 'infinite'}")
    print(f"  Error threshold: {error_threshold} consecutive before skip")
    print(f"  Timeout:         {timeout}s per request")
    print(f"  Started:         {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    healer = Healer()

    # Start services if needed
    print("\nStarting services...")
    await healer.start_all()
    status = await healer.ensure_all_healthy()
    for svc, (ok, detail) in status.items():
        icon = "OK" if ok else "DOWN"
        print(f"  {svc}: {icon} ({detail})")

    if not all(ok for ok, _ in status.values()):
        print("\nFATAL: Cannot start all services. Exiting.")
        healer.cleanup()
        sys.exit(1)

    # Resume state
    saved = load_state()
    start_cycle = 1
    if saved and start_batch == 1:
        start_cycle = saved.get("cycle", 1)
        start_batch = saved.get("batch", 1)
        print(f"\n  Resuming from cycle {start_cycle}, batch {start_batch}")

    all_cycle_reports: list[dict] = []
    total_incidents = 0

    try:
        cycle = start_cycle
        while max_cycles <= 0 or cycle <= max_cycles:
            seed = 42 + cycle  # different seed each cycle
            rng = random.Random(seed)
            cycle_start = time.time()

            print(f"\n{'#' * 60}")
            print(f"# CYCLE {cycle} — seed={seed}")
            print(f"# {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'#' * 60}")

            cycle_reports: list[BatchReport] = []
            batch1_sent: list = []
            batch1_prompts: list = []
            first_batch = start_batch if cycle == start_cycle else 1

            async with httpx.AsyncClient() as client:
                for batch_num in range(first_batch, 13):
                    save_state(cycle, batch_num, seed)

                    print(f"\n{'─' * 50}")
                    print(f"  Cycle {cycle} / Batch {batch_num}/12")
                    print(f"  {datetime.now().strftime('%H:%M:%S')}")
                    print(f"{'─' * 50}")

                    report, batch1_sent, batch1_prompts = await run_batch_with_healing(
                        batch_num, cycle, client, api_url, rng, healer,
                        batch1_sent, batch1_prompts, error_threshold,
                    )

                    if report:
                        print_batch_summary(report)
                        save_report(report, RESULTS_DIR)
                        cycle_reports.append(report)
                    else:
                        print(f"  Batch {batch_num} SKIPPED (unrecoverable)")

            # Cycle summary
            cycle_time = time.time() - cycle_start
            total_reqs = sum(r.total for r in cycle_reports)
            total_ok = sum(r.successes for r in cycle_reports)
            total_cached = sum(r.cache_hits for r in cycle_reports)
            total_err = sum(r.errors for r in cycle_reports)

            cycle_summary = {
                "cycle": cycle,
                "seed": seed,
                "duration_s": round(cycle_time, 1),
                "total_requests": total_reqs,
                "successes": total_ok,
                "cache_hits": total_cached,
                "errors": total_err,
                "batches_completed": len(cycle_reports),
                "batches_skipped": 12 - len(cycle_reports),
            }
            all_cycle_reports.append(cycle_summary)

            print(f"\n{'=' * 60}")
            print(f"  CYCLE {cycle} COMPLETE — {cycle_time/60:.1f} minutes")
            print(f"  Requests: {total_reqs} | OK: {total_ok} | "
                  f"Cached: {total_cached} | Errors: {total_err}")
            print(f"  Batches: {len(cycle_reports)}/12 completed")
            print(f"{'=' * 60}")

            # Save cumulative summary
            summary_path = RESULTS_DIR / "cumulative_summary.json"
            summary_path.write_text(json.dumps({
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "cycles": all_cycle_reports,
                "total_requests": sum(c["total_requests"] for c in all_cycle_reports),
                "total_successes": sum(c["successes"] for c in all_cycle_reports),
                "total_cached": sum(c["cache_hits"] for c in all_cycle_reports),
                "total_errors": sum(c["errors"] for c in all_cycle_reports),
            }, indent=2))

            # Count incidents this cycle
            if INCIDENT_LOG.exists():
                with open(INCIDENT_LOG) as f:
                    incidents = [json.loads(line) for line in f if line.strip()]
                cycle_incidents = [i for i in incidents if i.get("cycle") == cycle]
                if cycle_incidents:
                    print(f"\n  Incidents this cycle: {len(cycle_incidents)}")
                    for inc in cycle_incidents:
                        resolved = "FIXED" if inc["resolved"] else "UNFIXED"
                        print(f"    [{resolved}] {inc['error_type']}/{inc['service']}: {inc['diagnosis'][:60]}")
                    total_incidents += len(cycle_incidents)

            cycle += 1
            start_batch = 1  # reset for next cycle

            # Brief pause between cycles
            print(f"\n  Pausing 10s before cycle {cycle}...")
            await asyncio.sleep(10)

    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
    finally:
        # Final summary
        print(f"\n{'=' * 60}")
        print("  SELF-HEALING RUNNER — FINAL SUMMARY")
        print(f"{'=' * 60}")
        total_all = sum(c["total_requests"] for c in all_cycle_reports)
        total_ok = sum(c["successes"] for c in all_cycle_reports)
        total_cached = sum(c["cache_hits"] for c in all_cycle_reports)
        total_err = sum(c["errors"] for c in all_cycle_reports)
        print(f"  Cycles completed:  {len(all_cycle_reports)}")
        print(f"  Total requests:    {total_all}")
        print(f"  Successes:         {total_ok}")
        print(f"  Cache hits:        {total_cached}")
        print(f"  Errors:            {total_err}")
        print(f"  Incidents:         {total_incidents}")
        print(f"  Finished:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        healer.cleanup()
        save_state(cycle, 12, 0)  # mark complete


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BitMod Self-Healing Overnight Runner")
    parser.add_argument("--api-url", default=os.getenv("BITMOD_TEST_API_URL", f"https://test.bitmod.io"))
    parser.add_argument("--start-batch", type=int, default=1)
    parser.add_argument("--cycles", type=int, default=0, help="Max cycles (0=infinite)")
    parser.add_argument("--error-threshold", type=int, default=MAX_CONSECUTIVE_ERRORS)
    parser.add_argument("--timeout", type=float, default=REQUEST_TIMEOUT)
    args = parser.parse_args()

    asyncio.run(main(args.api_url, args.start_batch, args.cycles, args.error_threshold, args.timeout))
