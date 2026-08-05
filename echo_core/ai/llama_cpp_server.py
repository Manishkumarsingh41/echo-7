from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
import os
from pathlib import Path
import string
import socket
import subprocess
import time
from typing import Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from echo_core.config import AppConfig


USB_RUNTIME_ROOT = Path("USB-Uncensored-LLM") / "Shared"
USB_RUNTIME_EXE = USB_RUNTIME_ROOT / "bin" / "llama-server.exe"
USB_MODEL_FILE = USB_RUNTIME_ROOT / "models" / "Phi-3.5-mini-instruct-Q4_K_M.gguf"


class LlamaHealthState(str, Enum):
    READY = "ready"
    LOADING = "loading"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class LlamaCppInstallation:
    runtime_path: Path
    model_path: Path
    drive_root: Path | None
    model_label: str


@dataclass(frozen=True, slots=True)
class LlamaCppHealthCheck:
    state: LlamaHealthState
    status_code: int | None
    body: str = ""


@dataclass(frozen=True, slots=True)
class LlamaCppServerSession:
    installation: LlamaCppInstallation
    process: subprocess.Popen[bytes] | None
    owns_server: bool


@dataclass(frozen=True, slots=True)
class LlamaCppStartupResult:
    ready: bool
    installation: LlamaCppInstallation | None
    health: LlamaCppHealthCheck
    session: LlamaCppServerSession | None
    endpoint: str
    status_lines: tuple[str, ...]
    diagnostic: str = ""


class LlamaCppServerManager:
    """Discover and manage the local llama.cpp server on removable media."""

    def __init__(
        self,
        config: AppConfig,
        *,
        drive_roots: Callable[[], Iterable[Path]] | None = None,
        opener: Callable[..., object] = urlopen,
        popen_factory: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._drive_roots = drive_roots or self._default_drive_roots
        self._opener = opener
        self._popen_factory = popen_factory
        self._clock = clock
        self._sleep = sleep
        self._base_url = f"http://{config.llama_host}:{config.llama_port}"
        self._health_url = f"{self._base_url}/health"
        self._chat_completions_url = f"{self._base_url}/v1/chat/completions"

    @property
    def endpoint(self) -> str:
        return self._chat_completions_url

    def bootstrap(self) -> LlamaCppStartupResult:
        installation = self.discover_installation()
        if installation is None:
            return self._build_result(
                False,
                None,
                LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, None, "USB runtime/model not found."),
                None,
                diagnostic="runtime or model path is missing",
            )

        health = self.check_health()

        if health.state is LlamaHealthState.READY:
            session = self._build_session(installation, process=None, owns_server=False)
            return self._build_result(
                True,
                installation,
                health,
                session,
                diagnostic="compatible llama.cpp server already healthy on port 8080",
            )

        if health.state is LlamaHealthState.LOADING:
            ready_health = self.wait_for_ready(self._config.llama_startup_timeout_seconds)
            if ready_health.state is LlamaHealthState.READY:
                session = self._build_session(installation, process=None, owns_server=False)
                return self._build_result(
                    True,
                    installation,
                    ready_health,
                    session,
                    diagnostic="compatible llama.cpp server finished loading on port 8080",
                )
            return self._build_result(False, installation, ready_health, None, diagnostic=ready_health.body or "startup timed out while waiting for an already-loading server")

        if self._is_port_occupied():
            return self._build_result(
                False,
                installation,
                LlamaCppHealthCheck(
                    LlamaHealthState.UNAVAILABLE,
                    None,
                    "Port 8080 is already occupied by a non-compatible process.",
                ),
                None,
                diagnostic="port 8080 already occupied before launch; refusing to start a second server",
            )

        process = self._launch_server(installation)
        if process is None:
            return self._build_result(
                False,
                installation,
                LlamaCppHealthCheck(
                    LlamaHealthState.UNAVAILABLE,
                    None,
                    "llama-server could not be started.",
                ),
                None,
                diagnostic="llama-server process could not be started",
            )

        initial_returncode = process.poll()
        if initial_returncode is not None:
            return self._build_result(
                False,
                installation,
                LlamaCppHealthCheck(
                    LlamaHealthState.UNAVAILABLE,
                    initial_returncode,
                    "llama-server exited immediately after launch.",
                ),
                self._build_session(installation, process=process, owns_server=True),
                diagnostic=f"llama-server exited immediately with return code {initial_returncode}",
            )

        ready_health = self.wait_for_ready(
            self._config.llama_startup_timeout_seconds,
            process=process,
        )
        if ready_health.state is LlamaHealthState.READY:
            session = self._build_session(installation, process=process, owns_server=True)
            return self._build_result(
                True,
                installation,
                ready_health,
                session,
                diagnostic="ECHO brain is online",
            )

        session = self._build_session(installation, process=process, owns_server=True)
        self.shutdown(session)
        diagnostic = ready_health.body or "llama-server failed to become ready before timeout"
        return self._build_result(False, installation, ready_health, None, diagnostic=diagnostic)

    def discover_installation(self) -> LlamaCppInstallation | None:
        runtime_override = self._resolve_override(self._config.llama_runtime_path)
        model_override = self._resolve_override(self._config.llama_model_path)

        if runtime_override is not None and model_override is not None:
            if runtime_override.exists() and model_override.exists():
                return self._installation_from_paths(runtime_override, model_override)
            return None

        if runtime_override is not None and runtime_override.exists():
            candidate_model = self._find_model_for_root(runtime_override.anchor)
            if candidate_model is not None:
                return self._installation_from_paths(runtime_override, candidate_model)

        if model_override is not None and model_override.exists():
            candidate_runtime = self._find_runtime_for_root(model_override.anchor)
            if candidate_runtime is not None:
                return self._installation_from_paths(candidate_runtime, model_override)

        for root in self._unique_paths(self._drive_roots()):
            runtime_path = root / USB_RUNTIME_EXE
            model_path = root / USB_MODEL_FILE
            if runtime_path.exists() and model_path.exists():
                return self._installation_from_paths(runtime_path, model_path, root=root)

        return None

    def check_health(self) -> LlamaCppHealthCheck:
        try:
            request = Request(self._health_url, method="GET")
            with self._opener(request, timeout=self._config.llama_request_timeout_seconds) as response:
                status_code = int(getattr(response, "status", 200))
                body = self._read_body(response)
        except HTTPError as exc:
            body = self._read_http_error_body(exc)
            if exc.code == 503:
                return LlamaCppHealthCheck(LlamaHealthState.LOADING, exc.code, body)
            return LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, exc.code, body)
        except (URLError, TimeoutError, OSError, ValueError):
            return LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, None, "")

        if status_code == 200:
            return LlamaCppHealthCheck(LlamaHealthState.READY, status_code, body)
        if status_code == 503:
            return LlamaCppHealthCheck(LlamaHealthState.LOADING, status_code, body)
        return LlamaCppHealthCheck(LlamaHealthState.UNAVAILABLE, status_code, body)

    def wait_for_ready(
        self,
        timeout_seconds: float,
        *,
        process: subprocess.Popen[bytes] | None = None,
    ) -> LlamaCppHealthCheck:
        deadline = self._clock() + timeout_seconds
        last_health = self.check_health()
        if last_health.state is LlamaHealthState.READY:
            return last_health

        while self._clock() < deadline:
            if process is not None and process.poll() is not None:
                return LlamaCppHealthCheck(
                    LlamaHealthState.UNAVAILABLE,
                    process.returncode,
                    "llama-server exited before the model became ready.",
                )

            remaining_seconds = deadline - self._clock()
            if remaining_seconds <= 0:
                break

            self._sleep(min(self._config.llama_poll_interval_seconds, remaining_seconds))
            last_health = self.check_health()
            if last_health.state is LlamaHealthState.READY:
                return last_health

        if last_health.state is LlamaHealthState.LOADING:
            return LlamaCppHealthCheck(
                LlamaHealthState.UNAVAILABLE,
                last_health.status_code,
                "Local llama.cpp startup timed out.",
            )
        return last_health

    def shutdown(self, session: LlamaCppServerSession | None) -> None:
        if session is None or not session.owns_server or session.process is None:
            return
        if session.process.poll() is not None:
            return

        session.process.terminate()
        try:
            session.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            session.process.kill()
            try:
                session.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def _launch_server(self, installation: LlamaCppInstallation) -> subprocess.Popen[bytes] | None:
        command = [
            str(installation.runtime_path),
            "-m",
            str(installation.model_path),
            "--host",
            self._config.llama_host,
            "--port",
            str(self._config.llama_port),
            "-c",
            str(self._config.llama_context_size),
            "-t",
            str(self._config.llama_threads),
            "-ngl",
            str(self._config.llama_gpu_layers),
        ]

        creationflags = 0
        if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            return self._popen_factory(
                command,
                cwd=str(installation.runtime_path.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except OSError:
            return None

    def _build_result(
        self,
        ready: bool,
        installation: LlamaCppInstallation | None,
        health: LlamaCppHealthCheck,
        session: LlamaCppServerSession | None,
        *,
        diagnostic: str = "",
    ) -> LlamaCppStartupResult:
        status_lines = self._build_status_lines(installation, health)
        return LlamaCppStartupResult(
            ready=ready,
            installation=installation,
            health=health,
            session=session,
            endpoint=self.endpoint,
            status_lines=status_lines,
            diagnostic=diagnostic,
        )

    def _build_session(
        self,
        installation: LlamaCppInstallation | None,
        *,
        process: subprocess.Popen[bytes] | None,
        owns_server: bool,
    ) -> LlamaCppServerSession | None:
        if installation is None:
            return None
        return LlamaCppServerSession(
            installation=installation,
            process=process,
            owns_server=owns_server,
        )

    def _build_status_lines(
        self,
        installation: LlamaCppInstallation | None,
        health: LlamaCppHealthCheck,
    ) -> tuple[str, ...]:
        lines: list[str] = []
        if installation is not None:
            lines.append("ECHO Drive: Found")
            lines.append("Runtime: llama.cpp")
            lines.append(f"Model: {installation.model_label}")

        if health.state is LlamaHealthState.LOADING:
            lines.append("Loading local AI...")
            lines.append("This may take up to a few minutes.")
        elif health.state is LlamaHealthState.READY:
            lines.append("Brain: ONLINE")
            lines.append("Mode: Text")
        else:
            lines.append("Local ECHO brain unavailable.")
        return tuple(lines)

    def _installation_from_paths(
        self,
        runtime_path: Path,
        model_path: Path,
        *,
        root: Path | None = None,
    ) -> LlamaCppInstallation:
        return LlamaCppInstallation(
            runtime_path=runtime_path,
            model_path=model_path,
            drive_root=root,
            model_label=self._format_model_label(model_path),
        )

    @staticmethod
    def _format_model_label(model_path: Path) -> str:
        stem = model_path.stem
        if stem.startswith("Phi-3.5-mini-instruct"):
            return "Phi-3.5 Mini Instruct Q4"
        return stem.replace("_", " ").replace("-", " ").title()

    @staticmethod
    def _resolve_override(value: str) -> Path | None:
        stripped = value.strip()
        if not stripped:
            return None
        return Path(stripped).expanduser()

    @staticmethod
    def _read_body(response: object) -> str:
        reader = getattr(response, "read", None)
        if reader is None:
            return ""
        raw_body = reader()
        if isinstance(raw_body, bytes):
            return raw_body.decode("utf-8", errors="replace").strip()
        return str(raw_body).strip()

    @staticmethod
    def _read_http_error_body(exc: HTTPError) -> str:
        try:
            body = exc.read()
        except OSError:
            return ""
        return body.decode("utf-8", errors="replace").strip()

    def _is_port_occupied(self) -> bool:
        try:
            with socket.create_connection((self._config.llama_host, self._config.llama_port), timeout=0.25):
                return True
        except OSError:
            return False

    def _find_model_for_root(self, drive_root: str) -> Path | None:
        root_path = Path(drive_root)
        candidate = root_path / USB_MODEL_FILE
        return candidate if candidate.exists() else None

    def _find_runtime_for_root(self, drive_root: str) -> Path | None:
        root_path = Path(drive_root)
        candidate = root_path / USB_RUNTIME_EXE
        return candidate if candidate.exists() else None

    @staticmethod
    def _unique_paths(paths: Iterable[Path]) -> Sequence[Path]:
        seen: set[str] = set()
        ordered_paths: list[Path] = []
        for path in paths:
            key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            ordered_paths.append(path)
        return tuple(ordered_paths)

    @staticmethod
    def _default_drive_roots() -> Iterable[Path]:
        if os.name != "nt":
            return []

        try:
            import ctypes

            drive_bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            roots: list[Path] = []
            for index, letter in enumerate(string.ascii_uppercase):
                if drive_bitmask & (1 << index):
                    root = Path(f"{letter}:\\")
                    if ctypes.windll.kernel32.GetDriveTypeW(str(root)) == 2:
                        roots.append(root)
            return roots
        except Exception:
            return []
