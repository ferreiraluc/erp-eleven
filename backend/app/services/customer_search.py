"""Literal directory lookup, including documents on owner-confirmed aliases."""
from sqlalchemy import String, cast, or_, select, func
from sqlalchemy.orm import aliased

from ..models.cliente import Cliente
from .customer_documents import normalized_number


def directory_match(term):
    pattern = '%' + term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    document_number = normalized_number(term)
    document_query = len(document_number) >= 3 and any(char.isdigit() for char in document_number) and all(
        char.isalnum() or char in ' .-/()\t\n\r' for char in term)

    def normalized_document(column):
        # Portable SQL also covers CPF/CNPJ punctuation retained by old records.
        # Keep JSON delimiters: numbers from adjacent fields must not concatenate.
        value = func.upper(func.coalesce(column, ''))
        for separator in (' ', '.', '-', '/', '(', ')', '\t', '\n', '\r'):
            value = func.replace(value, separator, '')
        return value

    def fields(row):
        matches = [column.ilike(pattern, escape='\\') for column in (
            row.nome, row.email, row.telefone, row.cpf, row.endereco,
        )]
        # Document numbers are stored normalized. Avoid matching JSON field names
        # (e.g. searching "CI" must not return every Paraguayan document).
        if document_query:
            matches.extend((normalized_document(row.cpf).contains(document_number, autoescape=True),
                normalized_document(cast(row.documentos, String)).contains(document_number, autoescape=True)))
        return or_(*matches)

    alias = aliased(Cliente)
    # Maintenance rewrites direct links, but older aliases can form a chain. Their
    # identity remains on the original row; no copy or document overwrite here.
    identities = fields(alias)
    alias_ids = select(alias.id, alias.merged_into_id).where(
        alias.merged_into_id.is_not(None), identities,
    ).cte('matched_customer_aliases', recursive=True)
    parent = aliased(Cliente)
    # UNION distinct terminates even if an old, invalid alias chain has a cycle.
    # Cycles have no root and therefore cannot make another principal match.
    alias_ids = alias_ids.union(select(parent.id, parent.merged_into_id).join(
        alias_ids, parent.id == alias_ids.c.merged_into_id,
    ).where(parent.merged_into_id.is_not(None)))
    return or_(fields(Cliente), Cliente.id.in_(
        select(alias_ids.c.merged_into_id),
    ))
