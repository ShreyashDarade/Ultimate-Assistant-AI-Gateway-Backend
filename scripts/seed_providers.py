"""Seed the capability registry — validates all adapters load correctly."""

import asyncio

from app.providers.client_pool import ClientPool
from app.providers.registry import ProviderRegistry


async def main():
    print("Seeding provider registry...\n")

    pool = ClientPool()
    await pool.startup()

    registry = ProviderRegistry(pool)
    registry.load_all()

    print(f"Loaded {len(registry.providers)} providers:\n")
    for name, adapter in registry.providers.items():
        caps = adapter.get_capabilities()
        models = adapter.get_models()
        cap_strs = [f"  {k[0].value}→{k[1].value}" for k in caps.keys()]
        print(f"  {name}:")
        print(f"    Models: {len(models)}")
        print(f"    Capabilities:")
        for c in cap_strs:
            print(f"      {c}")
        print()

    print(f"\nCapability map ({len(registry.capability_map)} conversions):")
    for (in_mod, out_mod), pairs in registry.capability_map.items():
        print(f"  {in_mod.value}→{out_mod.value}: {len(pairs)} providers")
        for p, m in pairs:
            print(f"    - {p}/{m}")

    await pool.shutdown()
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
