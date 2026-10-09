"""Sandboxed command execution.

Runs each command as a child process with an explicit environment, a chroot-like
workspace cwd, and OS resource limits (CPU time, address space, file size,
process count). Commands never run with the API server's environment.

This provides process-level isolation only. For hard multi-tenant isolation run
the executor inside the provided Docker image (see docker/ and docs/sandbox-security.md).
"""
import os, resource, subprocess, signal, time

_BLOCKED_BINARIES = {"sudo", "su", "mount", "umount", "ssh", "scp", "iptables", "nsenter"}

def _shell() -> str:
    for s in ("/bin/bash", "/usr/bin/bash", "/bin/sh", "/usr/bin/sh", "/busybox/sh"):
        if os.path.exists(s):
            return s
    return "/bin/sh"

def _limit(cpu, mem_mb, fsize_mb, nproc=0):
    def fn():
        mem = mem_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_mb * 1024 * 1024,) * 2)
        if nproc:  # RLIMIT_NPROC is per-UID; skip on shared-UID hosts where it blocks every fork
            try: resource.setrlimit(resource.RLIMIT_NPROC, (nproc, nproc))
            except (ValueError, OSError): pass
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        os.setsid()
    return fn

def _clean_env(cwd, extra=None):
    env = {
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": cwd, "TERM": "xterm-256color", "LANG": "C.UTF-8",
        "PYTHONUNBUFFERED": "1", "npm_config_update_notifier": "false",
    }
    if extra: env.update({k: v for k, v in extra.items() if isinstance(k, str) and "=" not in k})
    return env

def run(cmd: str, cwd: str, timeout: int = 60, env_extra: dict | None = None,
        cpu=None, mem_mb=None) -> dict:
    first = cmd.strip().split()[0] if cmd.strip() else ""
    if os.path.basename(first) in _BLOCKED_BINARIES:
        return {"stdout": "", "stderr": f"blocked: '{first}' is not permitted in the sandbox", "exit_code": 126, "timed_out": False}
    start = time.time()
    try:
        p = subprocess.run(
            [_shell(), "-c", cmd], cwd=cwd,
            env=_clean_env(cwd, env_extra),
            capture_output=True, text=True, timeout=timeout,
            preexec_fn=_limit(cpu or 60, mem_mb or 768, 256),
        )
        return {"stdout": p.stdout[-200_000:], "stderr": p.stderr[-100_000:],
                "exit_code": p.returncode, "timed_out": False, "duration_s": round(time.time() - start, 2)}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"timed out after {timeout}s", "exit_code": 124, "timed_out": True,
                "duration_s": timeout}
    except Exception as e:
        return {"stdout": "", "stderr": f"exec error: {e}", "exit_code": 1, "timed_out": False}

class ShellSession:
    """A persistent interactive bash process: cwd and exported env survive between commands."""
    def __init__(self, cwd: str, cpu=None, mem_mb=None):
        self.cwd = cwd
        self.cpu = cpu or 60
        self.mem_mb = mem_mb or 768
        self.p = subprocess.Popen(
            [_shell(), "-i"] if _shell().endswith("bash") else [_shell(), "-i"],
            cwd=cwd, env=_clean_env(cwd),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            preexec_fn=_limit(self.cpu, self.mem_mb, 256),
            text=True, bufsize=1,
        )
        self.alive = True

    def run(self, cmd: str, timeout: int = 60) -> dict:
        if not self.alive or self.p.poll() is not None:
            return {"output": "", "exit_code": -1, "dead": True}
        marker = f"__OMNI_DONE_{os.getpid()}_{time.time_ns()}__"
        try:
            self.p.stdin.write(cmd + f"\n__omni_ec=$?; echo {marker} $__omni_ec\n")
            self.p.stdin.flush()
        except Exception:
            self.alive = False
            return {"output": "", "exit_code": -1, "dead": True}
        import selectors, time as _t
        sel = selectors.DefaultSelector(); sel.register(self.p.stdout, selectors.EVENT_READ)
        buf, deadline = [], _t.time() + timeout
        ec = None
        while _t.time() < deadline:
            for key, _ in sel.select(0.2):
                line = self.p.stdout.readline()
                if not line:
                    self.alive = False
                    return {"output": "".join(buf), "exit_code": -1, "dead": True}
                if line.startswith(marker):
                    ec = int(line.split()[-1]); break
                buf.append(line)
            if ec is not None: break
        if ec is None:
            return {"output": "".join(buf), "exit_code": None, "timed_out": True}
        return {"output": "".join(buf)[-200_000:], "exit_code": ec}

    def kill(self):
        try:
            os.killpg(os.getpgid(self.p.pid), signal.SIGKILL)
        except Exception:
            try: self.p.kill()
            except Exception: pass
