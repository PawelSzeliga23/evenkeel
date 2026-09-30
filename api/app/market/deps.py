"""The live market data providers, shared by the worker and the on-demand refresh; tests override the dependency."""
from collections.abc import Iterator

import httpx

from app.market.http import make_client
from app.market.providers.gus import GusInflationProvider
from app.market.providers.nbp import NbpFxProvider, NbpRefRateProvider
from app.market.providers.yahoo import YahooPriceProvider
from app.market.update import MarketProviders


def build_providers(client: httpx.Client) -> MarketProviders:
    return MarketProviders(
        prices=YahooPriceProvider(client),
        fx=NbpFxProvider(client),
        inflation=GusInflationProvider(client),
        ref_rates=NbpRefRateProvider(client),
    )


def get_market_providers() -> Iterator[MarketProviders]:
    with make_client() as client:
        yield build_providers(client)
