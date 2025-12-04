from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from Database.getConnection import getConnection as get_db
from models.favorites import Favorite, ProductType
from schemas.favorite import FavoriteCreate, FavoriteOut, FavoriteProductOut
from auth.authentication import get_current_user
from sqlalchemy import text

router = APIRouter(prefix="/favorites", tags=["Favorites"])

@router.get("/", response_model=list[FavoriteOut])
def list_favorites(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user["id"])
        .all()
    )


@router.post("/", response_model=FavoriteOut, status_code=status.HTTP_201_CREATED)
def add_favorite(
    data: FavoriteCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    fav = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == current_user["id"],
            Favorite.product_type == data.product_type,
            Favorite.product_id == data.product_id,
        )
        .first()
    )

    if fav:
        return fav  # idempotente

    fav = Favorite(
        user_id=current_user["id"],
        product_type=data.product_type,
        product_id=data.product_id,
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return fav


@router.delete("/{product_type}/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    product_type: ProductType,
    product_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    fav = (
        db.query(Favorite)
        .filter(
            Favorite.user_id == current_user["id"],
            Favorite.product_type == product_type,
            Favorite.product_id == product_id,
        )
        .first()
    )
    if not fav:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(fav)
    db.commit()

@router.get("/with-products", response_model=list[FavoriteProductOut])
def list_favorites_with_products(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    favorites = (
        db.query(Favorite)
        .filter(Favorite.user_id == current_user["id"])
        .all()
    )

    result: list[FavoriteProductOut] = []

    for fav in favorites:
        product_row = None

        if fav.product_type == ProductType.burger:
            product_row = db.execute(
                text(
                    "SELECT id_burger AS id, name, price, stock "
                    "FROM burger WHERE id_burger = :id"
                ),
                {"id": fav.product_id},
            ).mappings().first()

        elif fav.product_type == ProductType.drink:
            product_row = db.execute(
                text(
                    "SELECT id_drinks AS id, name, price, stock "
                    "FROM drinks WHERE id_drinks = :id"
                ),
                {"id": fav.product_id},
            ).mappings().first()

        elif fav.product_type == ProductType.fries:
            product_row = db.execute(
                text(
                    "SELECT id_fries AS id, name, price, stock "
                    "FROM fries WHERE id_fries = :id"
                ),
                {"id": fav.product_id},
            ).mappings().first()

        elif fav.product_type == ProductType.combo:
            product_row = db.execute(
                text(
                    "SELECT id_combos AS id, name, burger, drinks, fries, quantity, price"
                    "FROM combos WHERE id_combos = :id"
                ),
                {"id": fav.product_id},
            ).mappings().first()

        if not product_row:
            continue

        result.append(
            FavoriteProductOut(
                favorite_id=fav.id,
                product_type=fav.product_type,
                product_id=fav.product_id,
                name=product_row["name"],
                price=float(product_row["price"]),
                stock=int(product_row["stock"]),
            )
        )

    return result
