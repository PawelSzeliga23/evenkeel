import datetime as dt

from fastapi import APIRouter, Depends, Response

from app.catalog.schemas import CatalogAddIn, CatalogGroupOut, CatalogItemOut
from app.catalog.service import add_ticker, catalog
from app.market.deps import get_market_providers
from app.market.update import MarketProviders
from app.scoping import UserScope, get_scope

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.get("", response_model=list[CatalogGroupOut])
def get_catalog(scope: UserScope = Depends(get_scope)) -> list[CatalogGroupOut]:
    return catalog(scope)


@router.post("", response_model=CatalogItemOut, status_code=201)
def post_catalog(
    body: CatalogAddIn, response: Response, scope: UserScope = Depends(get_scope),
    providers: MarketProviders = Depends(get_market_providers),
) -> CatalogItemOut:
    item, created = add_ticker(scope.db, providers.prices, body.ticker, dt.datetime.now(dt.UTC))
    if not created:
        response.status_code = 200
    return item
