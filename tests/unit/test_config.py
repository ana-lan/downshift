import textwrap
from pathlib import Path

import pytest

from downshift.config import (
    Config,
    ConfigError,
    ModelPrice,
    ProviderConfig,
    load_config,
    parse_config,
    resolve_config,
)

ROOT = Path(__file__).resolve().parents[2]


def write(tmp_path: Path, text: str, name: str = "downshift.yaml") -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


# --- happy paths --------------------------------------------------------------


@pytest.mark.parametrize(
    "path", [ROOT / "downshift.example.yaml", ROOT / "examples/supportdesk/downshift.yaml"]
)
def test_shipped_configs_are_valid(path: Path) -> None:
    config = load_config(path)
    assert config.models.baseline == "qwen2.5:7b"
    for model in config.models.all_models:
        assert config.price_for(model).output_per_mtok >= 0


def test_empty_file_gives_defaults(tmp_path: Path) -> None:
    config = load_config(write(tmp_path, ""))
    assert config.models.baseline == "qwen2.5:7b"
    assert config.quality_threshold == 0.95
    assert config.scan.include == ("*.py",)
    assert config.source == tmp_path / "downshift.yaml"


def test_partial_config_keeps_other_defaults(tmp_path: Path) -> None:
    config = load_config(
        write(tmp_path, 'models: {baseline: "gpt-big", candidates: ["gpt-small"]}')
    )
    assert config.models.all_models == ("gpt-big", "gpt-small")
    assert config.provider.base_url == "http://localhost:11434/v1"


def test_judge_defaults_to_baseline() -> None:
    assert Config().models.judge_model == "qwen2.5:7b"
    config = parse_config({"models": {"judge": "qwen2.5:3b"}})
    assert config.models.judge_model == "qwen2.5:3b"


def test_volume_overrides_and_default() -> None:
    config = parse_config(
        {"volume": {"default_per_day": 100, "per_call_site": {"app.py::classify": 5000}}}
    )
    assert config.volume.calls_per_day("app.py::classify") == 5000
    assert config.volume.calls_per_day("app.py::other") == 100


def test_model_price_cost() -> None:
    price = ModelPrice(input_per_mtok=2.50, output_per_mtok=10.00)
    assert price.cost(1_000, 200) == pytest.approx(0.0045)
    assert price.cost(0, 0) == 0


def test_price_for_unknown_model_names_it() -> None:
    with pytest.raises(ConfigError, match="no pricing for model 'mystery'"):
        Config().price_for("mystery")


# --- validation errors --------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({"version": 2}, "version: unsupported value 2"),
        ({"modles": {}}, "modles: unknown key"),
        ({"provider": {"base_url": "localhost:11434"}}, "provider.base_url"),
        ({"provider": {"api_key_env": ""}}, "provider.api_key_env"),
        ({"provider": "ollama"}, "provider: must be a mapping"),
        ({"models": {"baseline": ""}}, "models.baseline"),
        ({"models": {"candidates": []}}, "at least one cheaper model"),
        ({"models": {"candidates": ["a", "a"]}}, "duplicate"),
        ({"models": {"baseline": "a", "candidates": ["a"]}}, "must not include the baseline"),
        ({"models": {"candidates": "small"}}, "models.candidates: must be a list"),
        ({"quality_threshold": 1.5}, "quality_threshold"),
        ({"quality_threshold": 0}, "quality_threshold"),
        ({"quality_threshold": True}, "quality_threshold"),
        ({"pricing": {"m": {"input": -1, "output": 1}}}, "pricing.m.input: must be a number >= 0"),
        ({"pricing": {"m": {"input": 1}}}, "pricing.m.output: missing"),
        ({"pricing": {"m": 5}}, "pricing.m: must be a mapping"),
        ({"pricing": {"m": {"input": 1, "output": 1, "cost": 2}}}, "pricing.m.cost: unknown key"),
        ({"volume": {"default_per_day": -1}}, "volume.default_per_day"),
        ({"volume": {"default_per_day": 1.5}}, "volume.default_per_day"),
        ({"volume": {"per_call_site": {"x": "lots"}}}, "volume.per_call_site.x"),
        ({"scan": {"include": []}}, "scan.include: must list at least one"),
        ({"scan": {"exclude": [3]}}, "scan.exclude"),
    ],
)
def test_invalid_values_are_reported(data: dict, expected: str) -> None:
    with pytest.raises(ConfigError) as info:
        parse_config(data)
    assert expected in str(info.value)


def test_all_problems_reported_together() -> None:
    with pytest.raises(ConfigError) as info:
        parse_config({"version": 9, "quality_threshold": 7, "scan": {"include": []}})
    message = str(info.value)
    assert "version" in message
    assert "quality_threshold" in message
    assert "scan.include" in message


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="top level must be a mapping"):
        load_config(write(tmp_path, "- just\n- a list\n"))


def test_invalid_yaml(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_config(write(tmp_path, "models: [unclosed\n"))


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_error_message_names_the_file(tmp_path: Path) -> None:
    path = write(tmp_path, "quality_threshold: 5\n")
    with pytest.raises(ConfigError, match=str(path)):
        load_config(path)


# --- discovery ----------------------------------------------------------------


def test_resolve_prefers_explicit_path(tmp_path: Path) -> None:
    explicit = write(tmp_path, "quality_threshold: 0.8\n", name="custom.yaml")
    write(tmp_path, "quality_threshold: 0.9\n")
    assert resolve_config(explicit, tmp_path).quality_threshold == 0.8


def test_resolve_discovers_file_in_directory(tmp_path: Path) -> None:
    write(tmp_path, "quality_threshold: 0.9\n")
    assert resolve_config(None, tmp_path).quality_threshold == 0.9


def test_resolve_discovers_next_to_a_file(tmp_path: Path) -> None:
    write(tmp_path, "quality_threshold: 0.9\n")
    target = tmp_path / "app.py"
    target.write_text("", encoding="utf-8")
    assert resolve_config(None, target).quality_threshold == 0.9


def test_resolve_falls_back_to_defaults(tmp_path: Path) -> None:
    config = resolve_config(None, tmp_path)
    assert config == Config()


# --- provider API key -----------------------------------------------------------


def test_api_key_not_needed_for_local_servers() -> None:
    assert ProviderConfig().api_key() == "not-needed"


def test_api_key_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_LLM_KEY", "secret")
    assert ProviderConfig(api_key_env="MY_LLM_KEY").api_key() == "secret"


def test_api_key_missing_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MY_LLM_KEY", raising=False)
    with pytest.raises(ConfigError, match="MY_LLM_KEY"):
        ProviderConfig(api_key_env="MY_LLM_KEY").api_key()


# --- min_pass_rate -----------------------------------------------------------


def test_min_pass_rate_defaults_to_off() -> None:
    from downshift.config import parse_config

    assert parse_config({"version": 1}).min_pass_rate == 0.0


def test_min_pass_rate_parsed() -> None:
    from downshift.config import parse_config

    assert parse_config({"version": 1, "min_pass_rate": 0.8}).min_pass_rate == 0.8
    assert parse_config({"version": 1, "min_pass_rate": 1}).min_pass_rate == 1.0


@pytest.mark.parametrize("value", [-0.1, 1.5, True, "high"])
def test_min_pass_rate_invalid(value: object) -> None:
    from downshift.config import ConfigError, parse_config

    with pytest.raises(ConfigError, match="min_pass_rate"):
        parse_config({"version": 1, "min_pass_rate": value})


def test_supportdesk_config_sets_floor() -> None:
    from pathlib import Path

    from downshift.config import load_config

    root = Path(__file__).resolve().parents[2]
    cfg = load_config(root / "examples" / "supportdesk" / "downshift.yaml")
    assert cfg.min_pass_rate == 0.8
    assert cfg.quality_threshold == 0.95
