from pixelator.ai.env import config_value, local_env_values


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
