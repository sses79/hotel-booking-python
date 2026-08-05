"""Reusable HTTP response construction."""

from fastapi.responses import JSONResponse
from pydantic import BaseModel


def model_json_response(*, status_code: int, model: BaseModel) -> JSONResponse:
    """Serialize a Pydantic model into a JSON response."""

    return JSONResponse(
        status_code=status_code,
        content=model.model_dump(mode="json"),
    )
