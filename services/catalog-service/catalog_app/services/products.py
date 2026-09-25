"""CRUD товаров."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from catalog_app.models import Product
from shared.contracts import ProductCreate, ProductUpdate
from shared.errors import ConflictError, NotFoundError


async def list_products(
    session: AsyncSession, *, offset: int = 0, limit: int = 50
) -> list[Product]:
    result = await session.scalars(select(Product).order_by(Product.id).offset(offset).limit(limit))
    return list(result)


async def get_product(session: AsyncSession, product_id: int) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")
    return product


async def create_product(session: AsyncSession, payload: ProductCreate) -> Product:
    existing = await session.scalar(select(Product).where(Product.sku == payload.sku))
    if existing is not None:
        raise ConflictError(f"SKU {payload.sku} already exists")
    product = Product(**payload.model_dump())
    session.add(product)
    await session.commit()
    await session.refresh(product)
    return product


async def update_product(session: AsyncSession, product_id: int, payload: ProductUpdate) -> Product:
    product = await get_product(session, product_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(product, field, value)
    await session.commit()
    await session.refresh(product)
    return product


async def delete_product(session: AsyncSession, product_id: int) -> None:
    product = await get_product(session, product_id)
    await session.delete(product)
    await session.commit()
