from pathlib import Path

from pixelator import __version__


def test_package_exposes_version():
    assert __version__ == "1.1.5"


def test_windows_package_script_exists_and_uses_pyinstaller():
    script = Path("scripts/package_windows.ps1")

    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "PyInstaller" in text
    assert "Pixelator.exe" in text
    assert "scripts/pixelator_gui_entry.py" in text.replace("\\", "/")
