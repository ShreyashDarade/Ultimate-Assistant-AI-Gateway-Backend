"""Provider registry — auto-discovers and loads all provider adapters.

Instead of hardcoded imports, this module scans `app/providers/*/adapter.py`
at startup and registers any `BaseProvider` subclass it finds.
Adding a new provider = create the folder + adapter.py. Zero imports needed.
"""

import importlib
import pkgutil

from app.core.logging import get_logger
from app.providers.base import BaseProvider
from app.providers.capabilities import CapabilityMap, build_capability_map
from app.providers.client_pool import ClientPool

logger = get_logger(__name__)


def discover_adapters() -> list[type[BaseProvider]]:
    """Auto-discover all provider adapter classes.

    Scans each sub-package of `app.providers` for an `adapter` module
    and collects any concrete `BaseProvider` subclass found within.
    """
    adapters: list[type[BaseProvider]] = []
    package = importlib.import_module("app.providers")

    for _, name, is_pkg in pkgutil.iter_modules(package.__path__):
        if not is_pkg:
            continue
        try:
            mod = importlib.import_module(f"app.providers.{name}.adapter")
            for attr_name in dir(mod):
                cls = getattr(mod, attr_name)
                if (
                    isinstance(cls, type)
                    and issubclass(cls, BaseProvider)
                    and cls is not BaseProvider
                    and hasattr(cls, "name")
                ):
                    adapters.append(cls)
                    logger.debug("adapter_discovered", adapter=cls.name, module=name)
        except ImportError as e:
            logger.debug("adapter_skip", module=name, reason=str(e))
        except Exception as e:
            logger.warning("adapter_discover_error", module=name, error=str(e))

    return adapters


class ProviderRegistry:
    """Loads all provider adapters and builds the capability map at startup."""

    def __init__(self, client_pool: ClientPool):
        self.client_pool = client_pool
        self.providers: dict[str, BaseProvider] = {}
        self.capability_map: CapabilityMap = {}

    def load_all(self) -> None:
        adapter_classes = discover_adapters()

        for cls in adapter_classes:
            try:
                client = self.client_pool.get(cls.name)
                adapter = cls(client)
                self.providers[adapter.name] = adapter
                logger.info("provider_loaded", provider=adapter.name)
            except Exception as e:
                logger.warning(
                    "provider_load_failed", provider=cls.name, error=str(e)
                )

        self.capability_map = build_capability_map(self.providers)
        total_caps = sum(len(v) for v in self.capability_map.values())
        logger.info(
            "capability_map_built",
            providers=len(self.providers),
            conversions=len(self.capability_map),
            total_entries=total_caps,
        )

    def get_provider(self, name: str) -> BaseProvider | None:
        return self.providers.get(name)

    def get_capable_providers(
        self, input_mod: str, output_mod: str
    ) -> list[tuple[str, str]]:
        """Return [(provider_name, model_id)] for a given modality conversion."""
        from app.providers.capabilities import Modality

        key = (Modality(input_mod), Modality(output_mod))
        return self.capability_map.get(key, [])
