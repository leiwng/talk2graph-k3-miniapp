"""LLM Provider 路由 & 降级。

- 注册全部 Provider；按 name 查找
- `default` 取 env DEFAULT_PROVIDER，缺省 "zhipu"
- 调用失败可在 fallback_chain 中顺序降级

W13-B 起：同一 Provider 类可注册多个实例（不同 model），用 name 区分。
"""
from __future__ import annotations

import os

from .base import LLMProvider
from .deepseek import DeepSeekProvider
from .kimi import KimiProvider
from .minimax import MiniMaxProvider
from .volcengine import VolcengineProvider
from .zhipu import ZhipuProvider


class LLMRouter:
    def __init__(self) -> None:
        # 基础 Provider（各 1 个实例，model 从 env 读）
        self._providers: dict[str, LLMProvider] = {
            "zhipu": ZhipuProvider(),
            "volcengine": VolcengineProvider(),
            "deepseek": DeepSeekProvider(),
            "minimax": MiniMaxProvider(),
        }

        # ----- 多 model 注册（同一 Provider 类不同实例） -----

        # 火山引擎 doubao 系列（共用 VOLCENGINE_API_KEY，model 直接用模型名）
        # 注意：doubao 用标准方舟 v3 端点，不是 GLM-5.2 的 coding/v3 端点
        volc_key = os.getenv("VOLCENGINE_API_KEY", "")
        volc_url_v3 = "https://ark.cn-beijing.volces.com/api/v3"
        for model_name, provider_name in [
            ("doubao-seed-2-1-pro-260628", "volcengine_doubao_pro"),
            ("doubao-seed-2-1-turbo-260628", "volcengine_doubao_turbo"),
        ]:
            p = VolcengineProvider(api_key=volc_key, model=model_name, base_url=volc_url_v3)
            p.name = provider_name
            self._providers[provider_name] = p

        # DeepSeek v4-pro（共用 DEEPSEEK_API_KEY）
        ds_key = os.getenv("DEEPSEEK_API_KEY", "")
        ds_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        p = DeepSeekProvider(api_key=ds_key, model="deepseek-v4-pro", base_url=ds_url)
        p.name = "deepseek_v4_pro"
        self._providers["deepseek_v4_pro"] = p

        # Kimi (Moonshot AI) — 3 个模型
        kimi_key = os.getenv("MOONSHOT_API_KEY", "")
        kimi_url = os.getenv("MOONSHOT_BASE_URL", "https://api.moonshot.cn/v1")
        for model_name, provider_name in [
            ("kimi-k2.6", "kimi_k26"),
            ("kimi-k2.7-code", "kimi_k27_code"),
            ("kimi-k2.7-code-highspeed", "kimi_k27_code_hs"),
        ]:
            p = KimiProvider(api_key=kimi_key, model=model_name, base_url=kimi_url)
            p.name = provider_name
            self._providers[provider_name] = p

        self.default = os.getenv("DEFAULT_PROVIDER", "zhipu")
        self.fallback_chain = list(self._providers.keys())

    def register(self, p: LLMProvider) -> None:
        self._providers[p.name] = p

    def get(self, name: str | None = None) -> LLMProvider:
        key = name or self.default
        if key not in self._providers:
            raise KeyError(f"unknown provider: {key}")
        return self._providers[key]

    def list_available(self) -> list[dict]:
        out = []
        for name, p in self._providers.items():
            out.append({
                "name": name,
                "model": getattr(p, "model", ""),
                "enabled": bool(getattr(p, "enabled", False)),
                "is_default": name == self.default,
            })
        return out


# 全局单例
_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter()
    return _router
