"""Look up real saved/printed addresses before preparing a confirmed print."""
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import defer

from ..models.address_book import SavedAddress
from ..models.printing import PrintJob
from .assistant_name_search import name_condition
from .assistant_queries import literal_pattern


def address_queries(db, term):
    addresses = db.query(SavedAddress).filter(SavedAddress.active.is_(True), SavedAddress.merged_into_id.is_(None))
    jobs = db.query(PrintJob).options(defer(PrintJob.pdf)).filter(PrintJob.snapshot.isnot(None), PrintJob.source.in_(('bot', 'erp')))
    if term in ('todos', 'remetentes'):
        return addresses, jobs, False
    names = (SavedAddress.label, SavedAddress.data['nome'].as_string())
    printed_names = (PrintJob.snapshot['editor']['nome'].as_string(), PrintJob.snapshot['endereco']['nome'].as_string())
    exact_addresses = addresses.filter(or_(
        SavedAddress.label.ilike(literal_pattern(term), escape='\\'),
        cast(SavedAddress.data, String).ilike(literal_pattern(term), escape='\\'),
        name_condition(db, names, term)))
    exact_jobs = jobs.filter(or_(cast(PrintJob.snapshot, String).ilike(literal_pattern(term), escape='\\'),
                                 name_condition(db, printed_names, term)))
    if (exact_addresses.with_entities(SavedAddress.id).limit(1).first() is not None
            or exact_jobs.with_entities(PrintJob.id).limit(1).first() is not None):
        return exact_addresses, exact_jobs, False
    # Only recipient names receive typo tolerance; never silently correct CEP,
    # CPF, street numbers or a sender nested elsewhere in the print snapshot.
    return (addresses.filter(name_condition(db, names, term, approximate=True)),
            jobs.filter(name_condition(db, printed_names, term, approximate=True)), True)
