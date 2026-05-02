"""fix clientes endereco to single field

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-05-02

Handles three possible DB states:
  1. clientes table doesn't exist yet          → g7h8i9j0k1l2 creates it correctly, this is no-op
  2. clientes table has old 5-column schema    → adds endereco, migrates data, drops old cols
  3. clientes table already has endereco col   → no-op
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


def upgrade():
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)

    # Se a tabela não existe, nada a fazer aqui (g7h8i9j0k1l2 já cria com schema correto)
    if 'clientes' not in inspector.get_table_names():
        return

    columns = [c['name'] for c in inspector.get_columns('clientes')]
    old_cols = ['endereco_rua', 'endereco_bairro', 'endereco_cidade', 'endereco_uf', 'endereco_cep']

    # Adicionar coluna única se não existir
    if 'endereco' not in columns:
        op.add_column('clientes', sa.Column('endereco', sa.Text()))

    # Migrar dados das colunas antigas para a nova
    existing_old = [c for c in old_cols if c in columns]
    if existing_old:
        parts = " || ', ' || ".join(
            f"COALESCE(NULLIF({c}, ''), '')" for c in existing_old
        )
        # Usa concat_ws para juntar partes não-vazias
        bind.execute(sa.text("""
            UPDATE clientes
            SET endereco = TRIM(BOTH ', ' FROM REGEXP_REPLACE(
                CONCAT_WS(', ',
                    NULLIF(TRIM(endereco_rua), ''),
                    NULLIF(TRIM(endereco_bairro), ''),
                    NULLIF(TRIM(endereco_cidade), ''),
                    NULLIF(TRIM(endereco_uf), ''),
                    NULLIF(TRIM(endereco_cep), '')
                ),
                '(, )+', ', ', 'g'
            ))
            WHERE endereco IS NULL OR endereco = ''
        """))

        for col in existing_old:
            op.drop_column('clientes', col)


def downgrade():
    bind = op.get_bind()
    inspector = reflection.Inspector.from_engine(bind)
    if 'clientes' not in inspector.get_table_names():
        return
    columns = [c['name'] for c in inspector.get_columns('clientes')]
    if 'endereco' in columns:
        op.drop_column('clientes', 'endereco')
    old_cols = {
        'endereco_rua': sa.String(255),
        'endereco_bairro': sa.String(100),
        'endereco_cidade': sa.String(100),
        'endereco_uf': sa.String(2),
        'endereco_cep': sa.String(9),
    }
    for col, typ in old_cols.items():
        if col not in columns:
            op.add_column('clientes', sa.Column(col, typ))
