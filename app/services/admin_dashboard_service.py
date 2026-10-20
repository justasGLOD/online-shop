
from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from ..crud.admin_dashboard_crud import get_dashboard_statistics
from ..extensions import db


class AdminDashboardError(Exception):
    """Raised when dashboard statistics cannot be loaded."""


def get_admin_dashboard_data():
    """Load dashboard statistics and handle database errors."""
    try:
        return get_dashboard_statistics()

    except SQLAlchemyError as error:
        db.session.rollback()
        current_app.logger.exception(
            "Failed to load admin dashboard statistics."
        )
        raise AdminDashboardError(
            "Dashboard statistics could not be loaded. Please try again."
        ) from error
