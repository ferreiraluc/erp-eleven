"""Resolve sender references against the current registry, never a conversation snapshot."""
import unicodedata

from ..models.printing import PrintSender


def _normalized(value):
    return ' '.join(''.join(
        character for character in unicodedata.normalize('NFKD', (value or '').casefold())
        if not unicodedata.combining(character)
    ).split())


def active_sender_catalog(db):
    """Callers must authorize access before reading the shared sender registry."""
    return db.query(PrintSender).filter_by(active=True).order_by(PrintSender.name, PrintSender.id).populate_existing().all()


def _names(sender):
    # The display name can be a short label; structured data holds the legal name.
    return {_normalized(sender.name), _normalized((sender.data or {}).get('nome'))} - {''}


def sender_candidates(db, reference, *, rows=None):
    """IDs are registered aliases; names may omit middle names, but not add guesses."""
    rows = active_sender_catalog(db) if rows is None else [row for row in rows if row.active]
    raw = (reference or '').strip()
    key = _normalized(raw)
    if not key:
        return []
    exact_id = [row for row in rows if row.id == raw]
    if exact_id:
        return exact_id
    matching_ids = [row for row in rows if _normalized(row.id) == key]
    if matching_ids:
        return matching_ids
    exact_name = [row for row in rows if key in _names(row)]
    if exact_name:
        return exact_name
    tokens = set(key.split())
    return [row for row in rows if any(tokens.issubset(name.split()) for name in _names(row))]


def sender_choices(rows):
    return [{'id': row.id, 'nome': row.name} for row in rows]


def resolve_sender(db, reference):
    """Return a current active sender or actionable choices; never choose a homonym."""
    rows = db.query(PrintSender).order_by(PrintSender.name, PrintSender.id).populate_existing().all()
    raw = (reference or '').strip()
    # An explicit disabled ID must not silently resolve to someone with a similar name.
    id_matches = [row for row in rows if row.id == raw]
    if not id_matches:
        id_matches = [row for row in rows if _normalized(row.id) == _normalized(raw)]
    if id_matches and not any(row.active for row in id_matches):
        return None, {
            'erro': 'Esse remetente está inativo no cadastro atual. Escolha um remetente ativo.',
            'codigo': 'remetente_inativo',
            'remetentes_disponiveis': sender_choices([row for row in rows if row.active]),
        }
    candidates = sender_candidates(db, reference, rows=rows)
    if len(candidates) == 1:
        return candidates[0], None
    if candidates:
        return None, {
            'erro': 'Encontrei mais de um remetente compatível. Informe qual deles deseja usar.',
            'codigo': 'remetente_ambiguo',
            'candidatos': sender_choices(candidates),
        }
    return None, {
        'erro': 'Consultei o cadastro atual e não identifiquei esse remetente. Confira os remetentes disponíveis.',
        'codigo': 'remetente_nao_encontrado',
        'remetentes_disponiveis': sender_choices([row for row in rows if row.active]),
    }
