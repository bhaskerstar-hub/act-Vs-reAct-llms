import time
from dataclasses import dataclass, field
from typing import Optional

from gateway.router import Router, RoutingPolicy


@dataclass
class ProviderStats:
    call_count:    int   = 0
    total_latency: float = 0.0
    total_cost:    float = 0.0
    error_count:   int   = 0

    @property
    def avg_latency(self) -> float:
        return self.total_latency / self.call_count if self.call_count else 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.call_count if self.call_count else 0.0


class LLMGateway:
    """
    Single entry point for all provider calls.
    Routes each request to the appropriate engine, records stats, and injects
    gateway_metadata into every result dict.
    """

    def __init__(self):
        from gateway.provider import FastProvider, StandardProvider, AdvancedProvider
        self._router = Router()
        self._providers = {
            "fast-engine":     FastProvider(),
            "standard-engine": StandardProvider(),
            "advanced-engine": AdvancedProvider(),
        }
        self._stats: dict[str, ProviderStats] = {
            name: ProviderStats() for name in self._providers
        }

    def execute(
        self,
        customer_id: str,
        message: str,
        policy: RoutingPolicy = RoutingPolicy.AUTO,
        _force_provider: Optional[str] = None,
    ) -> dict:
        provider_name, routing_reason = self._router.select(
            customer_id=customer_id,
            message=message,
            policy=policy,
        )
        if _force_provider and _force_provider in self._providers:
            provider_name  = _force_provider
            routing_reason = f"forced: {_force_provider}"

        provider = self._providers[provider_name]
        stats    = self._stats[provider_name]

        t0 = time.perf_counter()
        try:
            result     = provider.execute(customer_id=customer_id, message=message)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            stats.call_count    += 1
            stats.total_latency += elapsed_ms
            stats.total_cost    += provider.cost_per_call

            result["gateway_metadata"] = {
                "provider_name":  provider.name,
                "display_name":   provider.display_name,
                "routing_reason": routing_reason,
                "policy":         policy.value,
                "latency_ms":     round(elapsed_ms, 1),
                "cost":           provider.cost_per_call,
                "success":        True,
                "engine_type":    provider.engine_type,
            }
            return result
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            stats.error_count   += 1
            stats.total_latency += elapsed_ms
            raise

    def get_stats(self) -> dict:
        return {
            name: {
                "call_count":    s.call_count,
                "total_latency": round(s.total_latency, 1),
                "avg_latency":   round(s.avg_latency, 1),
                "total_cost":    round(s.total_cost, 6),
                "avg_cost":      round(s.avg_cost, 6),
                "error_count":   s.error_count,
            }
            for name, s in self._stats.items()
        }


_gateway_instance: Optional[LLMGateway] = None


def get_gateway() -> LLMGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = LLMGateway()
    return _gateway_instance
