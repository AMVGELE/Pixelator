import importlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from PIL import Image

from pixelator.layering import cli
from pixelator.layering.archive import write_layer_zip


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(SOURCE_ROOT)
        if not existing_pythonpath
        else str(SOURCE_ROOT) + os.pathsep + existing_pythonpath
    )
    return env


class FakeClient:
    def __init__(self, endpoint, api_key, poll_interval=2.0, timeout=600.0):
        self.endpoint = endpoint
        self.api_key = api_key

    def split_image(self, image_path, output_path, target_layers=None):
        image = Image.open(image_path).convert("RGBA")
        return write_layer_zip(image_path, image, [image], output_path, backend="fake", model_id="fake")


def test_project_scripts_point_to_importable_callables():
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    for script_name, entry_point in pyproject["project"]["scripts"].items():
        module_name, function_name = entry_point.split(":", maxsplit=1)
        module = importlib.import_module(module_name)
        target = module
        for attribute in function_name.split("."):
            target = getattr(target, attribute)

        assert callable(target), f"{script_name} target is not callable: {entry_point}"


def test_layering_cli_module_prints_root_help():
    result = subprocess.run(
        [sys.executable, "-m", "pixelator.layering.cli", "--help"],
        cwd=PROJECT_ROOT,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "pixelator-layer" in result.stdout
    assert "split" in result.stdout


def test_layering_cli_module_prints_split_help():
    result = subprocess.run(
        [sys.executable, "-m", "pixelator.layering.cli", "split", "--help"],
        cwd=PROJECT_ROOT,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "--endpoint" in result.stdout
    assert "--api-key-env" in result.stdout
    assert "--layers" in result.stdout
    assert "--overwrite" in result.stdout


def test_cli_splits_image_folder_and_writes_summary(monkeypatch, tmp_path: Path):
    first = tmp_path / "b.png"
    second = tmp_path / "a.jpg"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(first)
    Image.new("RGB", (3, 3), (0, 255, 0)).save(second)
    output_dir = tmp_path / "out"
    monkeypatch.setenv("PIXELATOR_LAYER_API_KEY", "secret")
    monkeypatch.setattr("pixelator.layering.commands.LayerSplitClient", FakeClient)

    exit_code = cli.main(["split", str(tmp_path), "--out", str(output_dir), "--endpoint", "http://service", "--overwrite"])

    assert exit_code == 0
    assert (output_dir / "a-layers.zip").exists()
    assert (output_dir / "b-layers.zip").exists()
    summary = json.loads((output_dir / "batch-summary.json").read_text(encoding="utf-8"))
    assert [item["source"] for item in summary["items"]] == [str(second), str(first)]
    assert all(item["status"] == "succeeded" for item in summary["items"])


def test_cli_requires_api_key(monkeypatch, tmp_path: Path, capsys):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    monkeypatch.delenv("PIXELATOR_LAYER_API_KEY", raising=False)

    exit_code = cli.main(["split", str(source), "--out", str(tmp_path / "out"), "--endpoint", "http://service"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "PIXELATOR_LAYER_API_KEY" in captured.err


def test_discover_images_accepts_single_image_and_rejects_non_images(tmp_path: Path):
    from pixelator.layering.commands import discover_images

    image = tmp_path / "hero.png"
    text = tmp_path / "notes.txt"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(image)
    text.write_text("ignore", encoding="utf-8")

    assert discover_images(image) == [image]
    assert discover_images(text) == []


def test_cli_fails_existing_output_without_overwrite(monkeypatch, tmp_path: Path):
    source = tmp_path / "hero.png"
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(source)
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (output_dir / "hero-layers.zip").write_bytes(b"old")
    monkeypatch.setenv("PIXELATOR_LAYER_API_KEY", "secret")
    monkeypatch.setattr("pixelator.layering.commands.LayerSplitClient", FakeClient)

    exit_code = cli.main(["split", str(source), "--out", str(output_dir), "--endpoint", "http://service"])

    summary = json.loads((output_dir / "batch-summary.json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert summary["failed"] == 1
    assert summary["items"][0]["status"] == "failed"
    assert (output_dir / "hero-layers.zip").read_bytes() == b"old"
