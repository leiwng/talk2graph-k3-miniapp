"""LLM Provider 路由 & 降级。

- 注册全部 Provider；按 name 查找
- `default` 取 env DEFAULT_PROVIDER，缺省 "zhipu"
- `fallback_chain`：调用失败时顺序降级（最多 3 个）
  - 由 `T2G_FALLBACK_PROVIDERS` env 配置（逗号分隔）
  - 未配置时自动取前 3 个 enabled provider
  - 第一个总是 default
- `is_retryable(err)`：判断错误是否触发 fallback

W13-B 起：同一 Provider 类可注册多个实例（不同 model），用 name 区分。
"""
from __future__ import annotations

import os

from .base import LLMError, LLMProvider
from .deepseek import DeepSeekProvider
from .kimi import KimiProvider
from .minimax import MiniMaxProvider
from .volcengine import VolcengineProvider
from .zhipu import ZhipuProvider


def is_retryable(err: Exception) -> bool:
    """是否触发 fallback：网络/超时、5xx、429 限流、4xx 鉴权失败、空响应。

    所有这些错误意味着"这次调用彻底没出有效结果"，可以换下一个 provider 重试。
    （4xx 鉴权失败也尝试切，因为可能是某家 Key 临时失效但其他家 OK。）
    """
    if isinstance(err, LLMError):
        # status=None：网络/超时
        # status>=500：服务端错误（含 503 / 529 限流）
        # status==429：客户端限流
        # status in (401, 403)：鉴权失败
        if err.status is None:
            return True
        if err.status >= 500:
            return True
        if err.status in (401, 403, 429):
            return True
        return False
    # 其他异常（如生成空响应被上层包成 ValueError）
    return True


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

        # 火山引擎 doubao：与 glm-5.2 共用 CodingPlan 的 coding/v3 端点与 API Key
        # （model_config_v02.md：火山方舟CodingPlan MODEL_LIST=[glm-5.2, Doubao-Seed-2.0-pro]）
        volc_key = os.getenv("VOLCENGINE_API_KEY", "")
        volc_url_coding = os.getenv(
            "VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/coding/v3"
        )
        for model_name, provider_name in [
            ("Doubao-Seed-2.0-pro", "volcengine_doubao_pro"),
        ]:
            p = VolcengineProvider(api_key=volc_key, model=model_name, base_url=volc_url_coding)
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
        self.fallback_chain = self._build_fallback_chain()

    def _build_fallback_chain(self) -> list[str]:
        """构造 fallback chain：最多 3 个 enabled provider，default 排第一。

        来源：
        1. env T2G_FALLBACK_PROVIDERS（逗号分隔）
        2. 未配置时：取 default + 其他 enabled，前 3 个
        """
        raw = os.getenv("T2G_FALLBACK_PROVIDERS", "").strip()
        chain: list[str] = []
        if raw:
            chain = [n.strip() for n in raw.split(",") if n.strip()]
        else:
            enabled = [
                name for name, p in self._providers.items()
                if getattr(p, "enabled", False)
            ]
            # default 排第一（若 enabled）
            if self.default in enabled:
                chain.append(self.default)
                for n in enabled:
                    if n != self.default:
                        chain.append(n)
            else:
                chain = enabled
        # 最多 3 个
        return chain[:3]

    def register(self, p: LLMProvider) -> None:
        self._providers[p.name] = p

    def get(self, name: str | None = None) -> LLMProvider:
        key = name or self.default
        if key not in self._providers:
            raise KeyError(f"unknown provider: {key}")
        return self._providers[key]

    def get_fallback_chain(self, start_with: str | None = None) -> list[LLMProvider]:
        """返回 fallback 链的 Provider 实例列表。

        start_with：若指定，则把它排第一（用于客户端显式选了某个 provider
        但仍希望后续 fallback 的场景）。生产模式下 start_with=None，使用 default。
        """
        if start_with and start_with in self._providers:
            names = [start_with] + [
                n for n in self.fallback_chain if n != start_with
            ]
        else:
            names = list(self.fallback_chain)
        return [self._providers[n] for n in names if n in self._providers]

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
