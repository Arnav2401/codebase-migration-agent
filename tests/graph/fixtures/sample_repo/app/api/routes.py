from typing import TYPE_CHECKING

from . import handlers
from ..models import User

if TYPE_CHECKING:
    from app.models.user import User as UserType


def get_user():
    return handlers.fetch()
