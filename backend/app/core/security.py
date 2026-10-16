from fastapi import HTTPException, Request


def client_identifier(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def reject_oversized_content_length(request: Request, max_bytes: int) -> None:
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > max_bytes + 65_536:
        raise HTTPException(status_code=413, detail="The request exceeds the configured upload limit.")
