"""百炼 Provider + T2G_FALLBACK_PROVIDERS（provider:model 格式）解析测试。"""
from __future__ import annotations

import pytest

from app.llm.bailian import BailianProvider
from app.llm.router import LLMRouter


def test_bailian_provider_defaults(monkeypatch):
    """百炼 Provider：默认 base_url / model，未配 key 时 disabled。"""
    monkeypatch.delenv("BAILIAN_API_KEY", raising=False)
    monkeypatch.delenv("BAILIAN_BASE_URL", raising=False)
    monkeypatch.delenv("BAILIAN_MODEL", raising=False)
    p = BailianProvider()
    assert p.name == "bailian"
    assert p.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert p.model == "qwen-max"
    assert p.enabled is False


def test_bailian_provider_enabled_with_key(monkeypatch):
    monkeypatch.setenv("BAILIAN_API_KEY", "sk-test")
    monkeypatch.setenv("BAILIAN_MODEL", "qwen3.8-max")
    p = BailianProvider()
    assert p.enabled is True
    assert p.model == "qwen3.8-max"


def test_fallback_spec_full_chain(monkeypatch):
    """5 个 provider:model 条目全部进入 chain（无 3 个上限），model 准确。"""
    monkeypatch.setenv(
        "T2G_FALLBACK_PROVIDERS",
        "deepseek:deepseek-v4-flash, bailian:qwen3.8-max, "
        "volcengine:glm-5.2, kimi:k3, minimax:MiniMax-M3",
    )
    r = LLMRouter()
    assert r.fallback_chain == [
        "deepseek:deepseek-v4-flash",
        "bailian:qwen3.8-max",
        "volcengine:glm-5.2",
        "kimi:k3",
        "minimax:MiniMax-M3",
    ]
    providers = r.get_fallback_chain()
    assert [p.model for p in providers] == [
        "deepseek-v4-flash",
        "qwen3.8-max",
        "glm-5.2",
        "k3",
        "MiniMax-M3",
    ]


def test_fallback_spec_missing_model(monkeypatch):
    """条目缺 model -> 启动即报错。"""
    monkeypatch.setenv("T2G_FALLBACK_PROVIDERS", "deepseek, bailian:qwen3.8-max")
    with pytest.raises(ValueError, match="缺少 model"):
        LLMRouter()


def test_fallback_spec_unknown_provider(monkeypatch):
    """未知 provider -> 启动即报错，并列出可选值。"""
    monkeypatch.setenv("T2G_FALLBACK_PROVIDERS", "openai:gpt-5")
    with pytest.raises(ValueError, match="未知 provider"):
        LLMRouter()


def test_fallback_spec_empty_model(monkeypatch):
    monkeypatch.setenv("T2G_FALLBACK_PROVIDERS", "deepseek:")
    with pytest.raises(ValueError, match="model 为空"):
        LLMRouter()


def test_fallback_unset_keeps_auto(monkeypatch):
    """未配置时回退到自动选 enabled（不报错）。"""
    monkeypatch.delenv("T2G_FALLBACK_PROVIDERS", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    r = LLMRouter()
    assert "deepseek" in r.fallback_chain
