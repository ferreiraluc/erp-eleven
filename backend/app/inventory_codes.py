"""Short public references; UUIDs and legacy SKUs remain the historical identity."""
import secrets

from sqlalchemy import Sequence, text
from .database import Base

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
CAPACITY = 32 ** 6
# An odd multiplier permutes the sequence without collisions within the capacity.
MULTIPLIER = 15485863
OFFSET = 32452843
sequence = Sequence('inventory_code_seq', start=1, maxvalue=CAPACITY, cycle=False, metadata=Base.metadata)


def encode_number(number):
    if not 1 <= number <= CAPACITY:
        raise ValueError('Limite de códigos do inventário atingido.')
    value = (number * MULTIPLIER + OFFSET) % CAPACITY
    result = ''
    for _ in range(6):
        result = ALPHABET[value % 32] + result
        value //= 32
    return 'INV-' + result


def new_inventory_code(context):
    connection = context.connection
    if connection.dialect.name == 'postgresql':
        return encode_number(connection.scalar(sequence))
    # SQLite is used in local tests; production allocates atomically via sequence.
    for _ in range(50):
        code = 'INV-' + ''.join(secrets.choice(ALPHABET) for _ in range(6))
        if not connection.execute(text('SELECT 1 FROM inventory_items WHERE inventory_code=:code'), {'code': code}).scalar():
            return code
    raise ValueError('Não foi possível reservar um código do inventário.')
