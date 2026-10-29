"""Keep old idempotency snapshots compatible with optional document metadata."""


def comparable_document_snapshot(value):
    if isinstance(value, dict):
        return {key: comparable_document_snapshot(item) for key, item in value.items()
                if item is not None or key not in {'documento_tipo', 'documento_emissor'}}
    if isinstance(value, list):
        return [comparable_document_snapshot(item) for item in value]
    return value
