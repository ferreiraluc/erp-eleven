"""Last-line log redaction, also applied to provider and exception messages."""
import logging
import re
from urllib.parse import urlsplit
from ..config import settings


def redact(message):
    value = str(message)
    for name in dir(settings):
        if any(word in name for word in ('SECRET','TOKEN','API_KEY','DATABASE_URL')):
            secret = getattr(settings,name)
            if isinstance(secret,str) and len(secret)>=6:value=value.replace(secret,'[REDACTED]')
    def url(match):
        try:
            parsed=urlsplit(match.group())
            return parsed.scheme+'://'+(parsed.hostname or '[host]')+'/[redacted]'
        except ValueError:return '[URL REDACTED]'
    value=re.sub(r'\b(?:https?|postgres(?:ql)?(?:\+psycopg2)?):\/\/[^\s<>"\']+',url,value)
    value=re.sub(r'(?i)\b(Bearer)\s+\S+',r'\1 [REDACTED]',value)
    value=re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b','[JWT REDACTED]',value)
    value=re.sub(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b','[EMAIL REDACTED]',value)
    value=re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b','[DOCUMENT REDACTED]',value)
    value=re.sub(r'(\s/[^\s?]*)\?[^\s]*',r'\1?[REDACTED]',value)
    return value


class RedactionFilter(logging.Filter):
    def filter(self,record):
        record.msg=redact(record.getMessage());record.args=()
        if record.exc_info:
            # Exception parameters can contain SQL values and provider payloads.
            # Keep class and frame positions, never exception values or locals.
            import traceback
            frames=traceback.extract_tb(record.exc_info[2])
            record.msg+=' exception='+record.exc_info[0].__name__+' frames='+','.join(f'{f.name}:{f.lineno}' for f in frames)
            record.exc_info=None;record.exc_text=None
        return True
