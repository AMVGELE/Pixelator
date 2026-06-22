from pixelator.ai.env import config_value, local_env_values, save_local_env_value


def test_config_value_reads_local_env_file_when_process_env_is_missing(monkeypatch, tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("DASHSCOPE_API_KEY=from_file\nIMAGE_MODEL='qwen-image-2.0'\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    local_env_values.cache_clear()

    assert config_value("DASHSCOPE_API_KEY") == "from_file"
    assert config_value("IMAGE_MODEL") == "qwen-image-2.0"


def test_process_env_takes_precedence_over_local_env_file(monkeypatch, tmp_path):
    (tmp_path / ".env.local").write_text("DASHSCOPE_API_KEY=from_file\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "from_process")
    local_env_values.cache_clear()

    assert config_value("DASHSCOPE_API_KEY") == "from_process"


def test_save_local_env_value_updates_env_file_and_current_process(monkeypatch, tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("IMAGE_MODEL=qwen-image-2.0\nDASHSCOPE_API_KEY=old\n", encoding="utf-8")
    monkeypatch.setenv("PIXELATOR_ENV_FILE", str(env_file))
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    local_env_values.cache_clear()

    saved_path = save_local_env_value("DASHSCOPE_API_KEY", "saved-key")

    assert saved_path == env_file
    assert "IMAGE_MODEL=qwen-image-2.0" in env_file.read_text(encoding="utf-8")
    assert "DASHSCOPE_API_KEY=saved-key" in env_file.read_text(encoding="utf-8")
    assert config_value("DASHSCOPE_API_KEY") == "saved-key"

    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    local_env_values.cache_clear()
    assert config_value("DASHSCOPE_API_KEY") == "saved-key"
