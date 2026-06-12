from pydantic import BaseModel


class CurrentUserResponse(BaseModel):
    id: str
    full_name: str
    email: str
    status: str
    allowed_channels: list[str]
