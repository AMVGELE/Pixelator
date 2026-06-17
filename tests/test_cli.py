from pathlib import Path

from pixelator import cli


def test_cli_requires_input(capsys):
    exit_code = cli.main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "usage:" in captured.err


def test_cli_dispatches_render(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")
    calls = {}

    def fake_render_media(input_file, output_file, config):
        calls["input"] = input_file
        calls["output"] = output_file
        calls["mode"] = config.mode
        output_path.write_bytes(b"rendered")
        return output_path

    monkeypatch.setattr(cli, "render_media", fake_render_media)

    exit_code = cli.main([str(input_path), "--mode", "fast", "--out", str(output_path), "--overwrite"])

    assert exit_code == 0
    assert calls["input"] == input_path
    assert calls["output"] == output_path
    assert calls["mode"] == "fast"


def test_cli_dispatches_crop_and_trim(monkeypatch, tmp_path: Path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")
    calls = {}

    def fake_render_media(input_file, output_file, config):
        calls["config"] = config
        output_path.write_bytes(b"rendered")
        return output_path

    monkeypatch.setattr(cli, "render_media", fake_render_media)

    exit_code = cli.main(
        [
            str(input_path),
            "--out",
            str(output_path),
            "--crop",
            "10,20,320,240",
            "--trim",
            "1.5,6.25",
            "--overwrite",
        ]
    )

    assert exit_code == 0
    assert calls["config"].crop.x == 10
    assert calls["config"].crop.y == 20
    assert calls["config"].crop.width == 320
    assert calls["config"].crop.height == 240
    assert calls["config"].trim.start == 1.5
    assert calls["config"].trim.end == 6.25


def test_cli_rejects_invalid_crop(capsys, tmp_path: Path):
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "output.mp4"
    input_path.write_bytes(b"fake")

    exit_code = cli.main([str(input_path), "--out", str(output_path), "--crop", "1,2,3"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--crop" in captured.err
