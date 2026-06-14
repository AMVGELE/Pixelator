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

    def fake_render_video(input_file, output_file, config):
        calls["input"] = input_file
        calls["output"] = output_file
        calls["mode"] = config.mode
        output_path.write_bytes(b"rendered")
        return output_path

    monkeypatch.setattr(cli, "render_video", fake_render_video)

    exit_code = cli.main([str(input_path), "--mode", "fast", "--out", str(output_path), "--overwrite"])

    assert exit_code == 0
    assert calls["input"] == input_path
    assert calls["output"] == output_path
    assert calls["mode"] == "fast"
