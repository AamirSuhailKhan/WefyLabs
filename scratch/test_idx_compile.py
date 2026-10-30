from sqlalchemy.schema import CreateIndex
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

t = sa.Table("test_table", sa.MetaData(), sa.Column("id", sa.Integer))
idx = sa.Index("ix_test_id", t.c.id)
c_idx = CreateIndex(idx, if_not_exists=True)
compiled = str(c_idx.compile(dialect=postgresql.dialect()))
print(f"Compiled Index DDL: {compiled}")
