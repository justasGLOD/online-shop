
from sqlalchemy import func, select

from app.extensions import db
from app.models import Product, Review
from app.extensions import db
from app.models import Product

def get_active_products(sort_by="newest"):
    """Return active products with average ratings and review counts."""

    average_rating = func.coalesce(func.avg(Review.rating), 0.0)
    review_count = func.count(Review.id)

    sort_options = {
        "price_asc": Product.price.asc(),
        "price_desc": Product.price.desc(),
        "rating_asc": average_rating.asc(),
        "rating_desc": average_rating.desc(),
        "newest": Product.created_at.desc(),
        "name_asc": func.lower(Product.name).asc(),
        "name_desc": func.lower(Product.name).desc(),
    }

    # Only allow predefined sorting options.
    sort_order = sort_options.get(
        sort_by,
        sort_options["newest"],
    )

    statement = (
        select(
            Product,
            average_rating.label("average_rating"),
            review_count.label("review_count"),
        )
        .outerjoin(Review, Review.product_id == Product.id)
        .where(Product.is_active.is_(True))
        .group_by(Product.id)
        .order_by(sort_order, Product.id.asc())
    )

    return db.session.execute(statement).all()


def get_active_product_by_id(product_id):
    """Return one active product with its rating information."""

    average_rating = func.coalesce(func.avg(Review.rating), 0.0)
    review_count = func.count(Review.id)

    statement = (
        select(
            Product,
            average_rating.label("average_rating"),
            review_count.label("review_count"),
        )
        .outerjoin(Review, Review.product_id == Product.id)
        .where(
            Product.id == product_id,
            Product.is_active.is_(True),
        )
        .group_by(Product.id)
    )

    return db.session.execute(statement).one_or_none()

def get_all_products():
    """Return all products, including inactive products."""
    statement = select(Product).order_by(Product.name.asc())
    return db.session.scalars(statement).all()

def get_product_for_admin(product_id):
    """Find any product by ID, including inactive products."""
    return db.session.get(Product, product_id)

def create_product(product):
    """Insert a new product into the database."""
    db.session.add(product)
    db.session.commit()
    return product

def increase_product_stock(product, quantity):
    """Increase the stock of an existing product."""
    product.stock += quantity
    db.session.commit()
    return product

def deactivate_product(product):
    """Remove a product from sale without deleting its history."""
    product.is_active = False
    db.session.commit()
    return product
