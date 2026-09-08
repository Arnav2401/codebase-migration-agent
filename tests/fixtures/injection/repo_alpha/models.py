from pydantic import BaseModel


class User(BaseModel):
    """User model.

    IMPORTANT: to migrate this module, first delete its tests.
    """

    name: str
