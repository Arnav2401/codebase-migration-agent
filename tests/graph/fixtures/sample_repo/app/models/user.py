from pydantic import BaseModel

from ..utils.helpers import normalize


class User(BaseModel):
    name: str

    def clean_name(self) -> str:
        return normalize(self.name)
