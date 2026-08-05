from __future__ import annotations

from dataclasses import dataclass
import argparse
import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable


SELF_TEST_CODE = (
    "import apps.desktop.main, echo_core.ai.base, echo_core.ai.llama_cpp_provider, "
    "echo_core.ai.llama_cpp_server, echo_core.config, echo_core.conversation; print('ok')"
)


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    total_memory_bytes: int
    available_memory_bytes: int
    logical_processors: int
    nvidia_gpu_available: bool


@dataclass(frozen=True, slots=True)
class LaunchSettings:
    context_size: int
    threads: int
    max_output_tokens: int
    startup_timeout_seconds: float
    gpu_layers: int


@dataclass(frozen=True, slots=True)
class EnvironmentChoice:
    python_executable: Path
    source: str
    created: bool = False


@dataclass(frozen=True, slots=True)
class UsbLayout:
    usb_root: Path
    app_root: Path
    runtime_executable: Path
    model_path: Path
    venv_python: Path


def resolve_usb_layout(usb_root: Path) -> UsbLayout:
    usb_root = normalize_usb_root(usb_root)
    app_root = usb_root / "ECHO-7"
    runtime_executable = usb_root / "USB-Uncensored-LLM" / "Shared" / "bin" / "llama-server.exe"
    model_path = usb_root / "USB-Uncensored-LLM" / "Shared" / "models" / "Phi-3.5-mini-instruct-Q4_K_M.gguf"
    venv_python = app_root / ".venv" / "Scripts" / "python.exe"
    return UsbLayout(
        usb_root=usb_root,
        app_root=app_root,
        runtime_executable=runtime_executable,
        model_path=model_path,
        venv_python=venv_python,
    )


def normalize_usb_root(usb_root: Path) -> Path:
    normalized = str(usb_root).strip().replace("/", "\\")
    if (
        len(normalized) in {2, 3}
        and len(normalized) >= 2
        and normalized[1] == ":"
    ):
        return Path(f"{normalized[0].upper()}:\\")
    return Path(normalized)


def detect_hardware_profile() -> HardwareProfile:
    memory_status = _memory_status()
    logical_processors = os.cpu_count() or 1
    nvidia_gpu_available = _detect_nvidia_gpu()
    return HardwareProfile(
        total_memory_bytes=memory_status["total"],
        available_memory_bytes=memory_status["available"],
        logical_processors=logical_processors,
        nvidia_gpu_available=nvidia_gpu_available,
    )


def choose_launch_settings(profile: HardwareProfile) -> LaunchSettings:
    total_gb = profile.total_memory_bytes / (1024**3)
    available_gb = profile.available_memory_bytes / (1024**3)

    if total_gb < 8.0 or available_gb < 4.0:
        return LaunchSettings(
            context_size=1024,
            threads=max(2, min(2, profile.logical_processors)),
            max_output_tokens=192,
            startup_timeout_seconds=240.0,
            gpu_layers=0,
        )

    return LaunchSettings(
        context_size=2048,
        threads=max(2, min(4, profile.logical_processors // 2 or 2)),
        max_output_tokens=256,
        startup_timeout_seconds=180.0,
        gpu_layers=0,
    )


def validate_python_interpreter(python_executable: Path, project_root: Path) -> bool:
    if not python_executable.exists():
        return False

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project_root)
    result = subprocess.run(
        [str(python_executable), "-c", SELF_TEST_CODE],
        cwd=str(project_root),
        env=environment,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def select_python_environment(
    layout: UsbLayout,
    project_root: Path,
    cache_root: Path,
    base_python: Path,
    *,
    self_test: Callable[[Path, Path], bool] = validate_python_interpreter,
) -> EnvironmentChoice:
    usb_python = layout.venv_python
    if usb_python.exists() and self_test(usb_python, project_root):
        return EnvironmentChoice(usb_python, "usb")

    cached_python = cache_root / ".venv" / "Scripts" / "python.exe"
    if cached_python.exists() and self_test(cached_python, project_root):
        return EnvironmentChoice(cached_python, "cached")

    created_python = ensure_cached_environment(base_python, cache_root, project_root)
    if not self_test(created_python, project_root):
        raise RuntimeError("Cached host environment failed the ECHO self-test.")
    return EnvironmentChoice(created_python, "created", created=True)


def ensure_cached_environment(base_python: Path, cache_root: Path, project_root: Path) -> Path:
    venv_root = cache_root / ".venv"
    python_executable = venv_root / "Scripts" / "python.exe"
    requirements_path = project_root / "requirements.txt"
    marker_path = cache_root / ".requirements.sha256"

    if not python_executable.exists():
        cache_root.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(base_python), "-m", "venv", str(venv_root)], check=True)

    requirements_hash = _hash_file(requirements_path) if requirements_path.exists() else ""
    marker_value = marker_path.read_text(encoding="utf-8").strip() if marker_path.exists() else ""

    if requirements_hash and requirements_hash != marker_value:
        _install_requirements(python_executable, requirements_path, project_root)
        marker_path.write_text(requirements_hash, encoding="utf-8")

    return python_executable


def run_portable_launcher(usb_root: Path, *, base_python: Path | None = None) -> int:
    usb_root = normalize_usb_root(usb_root)
    layout = resolve_usb_layout(usb_root)
    project_root = layout.app_root
    cache_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ECHO-7-Runtime"
    base_python = base_python or Path(sys.executable)

    print("==========================================")
    print("                 ECHO-7")
    print("==========================================")
    print()
    print("Checking system...")

    if not project_root.exists():
        print("ECHO-7 application not found on this USB.")
        return 1
    if not layout.runtime_executable.exists():
        print("llama-server.exe not found on this USB.")
        return 1
    if not layout.model_path.exists():
        print("Phi-3.5 model not found on this USB.")
        return 1

    hardware_profile = detect_hardware_profile()
    launch_settings = choose_launch_settings(hardware_profile)

    print("Preparing environment...")
    try:
        environment_choice = select_python_environment(
            layout,
            project_root,
            cache_root,
            base_python,
        )
    except Exception as exc:
        print("ECHO local environment could not be prepared.")
        print(f"Reason: {exc}")
        return 1

    print("USB: Connected")
    print("Application: Ready")
    print("Environment: Ready")
    print("System: Compatible")
    print()
    print("Finding ECHO brain...")

    environment = os.environ.copy()
    environment["PYTHONUNBUFFERED"] = "1"
    environment["ECHO_AI_PROVIDER"] = "auto"
    environment["ECHO_LLAMA_RUNTIME_PATH"] = str(layout.runtime_executable)
    environment["ECHO_LLAMA_MODEL_PATH"] = str(layout.model_path)
    environment["ECHO_LLAMA_HOST"] = "127.0.0.1"
    environment["ECHO_LLAMA_PORT"] = "8080"
    environment["ECHO_LLAMA_CONTEXT_SIZE"] = str(launch_settings.context_size)
    environment["ECHO_LLAMA_THREADS"] = str(launch_settings.threads)
    environment["ECHO_LLAMA_GPU_LAYERS"] = str(launch_settings.gpu_layers)
    environment["ECHO_LLAMA_STARTUP_TIMEOUT_SECONDS"] = str(launch_settings.startup_timeout_seconds)
    environment["ECHO_LLAMA_REQUEST_TIMEOUT_SECONDS"] = "180"
    environment["ECHO_LLAMA_MAX_OUTPUT_TOKENS"] = str(launch_settings.max_output_tokens)
    environment["ECHO_LLAMA_CONTEXT_RETRY_SAFETY_TOKENS"] = "128"
    environment["ECHO_DEFAULT_MODE"] = "Text"

    result = subprocess.run(
        [str(environment_choice.python_executable), "-u", "-m", "apps.desktop.main"],
        cwd=str(project_root),
        env=environment,
    )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ECHO-7 portable launcher")
    parser.add_argument("--usb-root", required=True, help="Root path of the USB drive")
    args = parser.parse_args(argv)
    return run_portable_launcher(Path(args.usb_root))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _install_requirements(python_executable: Path, requirements_path: Path, project_root: Path) -> None:
    subprocess.run(
        [str(python_executable), "-m", "pip", "install", "-r", str(requirements_path)],
        cwd=str(project_root),
        check=True,
    )


def _memory_status() -> dict[str, int]:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
    return {"total": int(status.ullTotalPhys), "available": int(status.ullAvailPhys)}


def _detect_nvidia_gpu() -> bool:
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return False
    try:
        result = subprocess.run([nvidia_smi, "-L"], capture_output=True, text=True)
    except OSError:
        return False
    return result.returncode == 0 and "GPU" in result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
