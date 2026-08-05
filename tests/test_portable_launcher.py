from __future__ import annotations

from pathlib import Path

from echo_core.portable_launcher import (
    EnvironmentChoice,
    HardwareProfile,
    UsbLayout,
    choose_launch_settings,
    detect_hardware_profile,
    resolve_usb_layout,
    run_portable_launcher,
    select_python_environment,
)


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    return path


def test_resolve_usb_layout_uses_dynamic_drive_root():
    layout = resolve_usb_layout(Path("F:\\"))

    assert layout.usb_root == Path("F:\\")
    assert layout.app_root == Path("F:\\") / "ECHO-7"
    assert layout.runtime_executable == Path("F:\\") / "USB-Uncensored-LLM" / "Shared" / "bin" / "llama-server.exe"
    assert layout.model_path == Path("F:\\") / "USB-Uncensored-LLM" / "Shared" / "models" / "Phi-3.5-mini-instruct-Q4_K_M.gguf"


def test_choose_launch_settings_for_low_memory_profile():
    profile = HardwareProfile(
        total_memory_bytes=6 * 1024**3,
        available_memory_bytes=2 * 1024**3,
        logical_processors=8,
        nvidia_gpu_available=False,
    )

    settings = choose_launch_settings(profile)

    assert settings.context_size == 1024
    assert settings.threads == 2
    assert settings.max_output_tokens == 192
    assert settings.startup_timeout_seconds == 240.0
    assert settings.gpu_layers == 0


def test_choose_launch_settings_for_normal_profile():
    profile = HardwareProfile(
        total_memory_bytes=16 * 1024**3,
        available_memory_bytes=8 * 1024**3,
        logical_processors=8,
        nvidia_gpu_available=False,
    )

    settings = choose_launch_settings(profile)

    assert settings.context_size == 2048
    assert settings.threads == 4
    assert settings.max_output_tokens == 256
    assert settings.startup_timeout_seconds == 180.0
    assert settings.gpu_layers == 0


def test_select_python_environment_accepts_usb_environment(tmp_path):
    project_root = tmp_path / "ECHO-7"
    cache_root = tmp_path / "cache"
    layout = resolve_usb_layout(tmp_path / "USB")
    _touch(layout.venv_python)
    _touch(cache_root / ".venv" / "Scripts" / "python.exe")

    def self_test(python_executable: Path, project_root: Path) -> bool:
        return python_executable == layout.venv_python

    choice = select_python_environment(
        layout,
        project_root,
        cache_root,
        base_python=Path("C:/Python/python.exe"),
        self_test=self_test,
    )

    assert choice.source == "usb"
    assert choice.python_executable == layout.venv_python


def test_select_python_environment_reuses_cached_environment(tmp_path):
    project_root = tmp_path / "ECHO-7"
    cache_root = tmp_path / "cache"
    layout = resolve_usb_layout(tmp_path / "USB")
    _touch(layout.venv_python)
    cached_python = _touch(cache_root / ".venv" / "Scripts" / "python.exe")

    def self_test(python_executable: Path, project_root: Path) -> bool:
        return python_executable == cached_python

    choice = select_python_environment(
        layout,
        project_root,
        cache_root,
        base_python=Path("C:/Python/python.exe"),
        self_test=self_test,
    )

    assert choice.source == "cached"
    assert choice.python_executable == cached_python


def test_select_python_environment_creates_cached_environment_when_needed(tmp_path, monkeypatch):
    project_root = tmp_path / "ECHO-7"
    cache_root = tmp_path / "cache"
    layout = resolve_usb_layout(tmp_path / "USB")
    _touch(layout.venv_python)
    created_python = cache_root / ".venv" / "Scripts" / "python.exe"
    calls: list[Path] = []

    def self_test(python_executable: Path, project_root: Path) -> bool:
        calls.append(python_executable)
        return python_executable == created_python

    def fake_ensure_cached_environment(base_python: Path, cache_root: Path, project_root: Path) -> Path:
        _touch(created_python)
        return created_python

    monkeypatch.setattr("echo_core.portable_launcher.ensure_cached_environment", fake_ensure_cached_environment)

    choice = select_python_environment(
        layout,
        project_root,
        cache_root,
        base_python=Path("C:/Python/python.exe"),
        self_test=self_test,
    )

    assert choice.source == "created"
    assert choice.created is True
    assert choice.python_executable == created_python
    assert calls[-1] == created_python


def test_run_portable_launcher_passes_conservative_environment_settings(tmp_path, monkeypatch, capsys):
    usb_root = tmp_path / "USB"
    layout = resolve_usb_layout(usb_root)
    _touch(layout.app_root / "apps" / "desktop" / "main.py")
    _touch(layout.runtime_executable)
    _touch(layout.model_path)

    recorded: dict[str, object] = {}

    def fake_detect_hardware_profile() -> HardwareProfile:
        return HardwareProfile(
            total_memory_bytes=6 * 1024**3,
            available_memory_bytes=2 * 1024**3,
            logical_processors=8,
            nvidia_gpu_available=False,
        )

    def fake_select_python_environment(layout_arg, project_root_arg, cache_root_arg, base_python_arg, self_test=...):
        return EnvironmentChoice(Path("C:/Python/python.exe"), "cached")

    def fake_subprocess_run(command, cwd=None, env=None, check=False, capture_output=False, text=False):
        recorded["command"] = command
        recorded["cwd"] = cwd
        recorded["env"] = env

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr("echo_core.portable_launcher.detect_hardware_profile", fake_detect_hardware_profile)
    monkeypatch.setattr("echo_core.portable_launcher.select_python_environment", fake_select_python_environment)
    monkeypatch.setattr("echo_core.portable_launcher.subprocess.run", fake_subprocess_run)

    exit_code = run_portable_launcher(usb_root, base_python=Path("C:/Python/python.exe"))

    assert exit_code == 0
    assert recorded["command"][0] == str(Path("C:/Python/python.exe"))
    assert recorded["command"][1] == "-u"
    assert recorded["command"][2] == "-m"
    assert recorded["command"][3] == "apps.desktop.main"
    assert recorded["env"]["ECHO_LLAMA_CONTEXT_SIZE"] == "1024"
    assert recorded["env"]["ECHO_LLAMA_THREADS"] == "2"
    assert recorded["env"]["ECHO_LLAMA_MAX_OUTPUT_TOKENS"] == "192"
    assert recorded["env"]["ECHO_LLAMA_STARTUP_TIMEOUT_SECONDS"] == "240.0"
    assert "Checking system..." in capsys.readouterr().out


def test_run_portable_launcher_rejects_missing_model(tmp_path, capsys):
    usb_root = tmp_path / "USB"
    layout = resolve_usb_layout(usb_root)
    _touch(layout.app_root / "apps" / "desktop" / "main.py")
    _touch(layout.runtime_executable)

    exit_code = run_portable_launcher(usb_root, base_python=Path("C:/Python/python.exe"))

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "Phi-3.5 model not found" in output


def test_run_portable_launcher_rejects_missing_runtime(tmp_path, capsys):
    usb_root = tmp_path / "USB"
    layout = resolve_usb_layout(usb_root)
    _touch(layout.app_root / "apps" / "desktop" / "main.py")
    _touch(layout.model_path)

    exit_code = run_portable_launcher(usb_root, base_python=Path("C:/Python/python.exe"))

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "llama-server.exe not found" in output
