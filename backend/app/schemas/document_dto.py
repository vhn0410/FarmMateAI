from pydantic import BaseModel, Field


class SyncResponse(BaseModel):
    """
    Schema defining the response payload returned by the document sync API.
    """

    status: str = Field(
        ...,
        json_schema_extra={"example": "success"},
        description="Status of the background process (for example: success, pending, error)",
    )
    message: str = Field(
        ...,
        json_schema_extra={"example": "The system is processing the documents in the background."},
        description="Detailed status message sent to the user or frontend",
    )
