from pydantic import BaseModel


class AddKeyRequest(BaseModel):
    provider: str
    api_key: str
    label: str = "default"


class KeyResponse(BaseModel):
    id: str
    provider: str
    label: str
    last4: str
    is_valid: bool
    created_at: str

    model_config = {"from_attributes": True}
