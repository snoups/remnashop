from pydantic import BaseModel


class SendTestEmailRequest(BaseModel):
    bulk: bool = False
