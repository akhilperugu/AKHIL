from app.schemas.comparison import Evidence


def evidence_for(source_text: str | None, field: str, explanation: str) -> list[Evidence]:
    if not source_text:
        return []
    return [Evidence(source_text=source_text, field=field, explanation=explanation)]
