from alembic.ddl.base import AddColumn
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

col = sa.Column("description", sa.Text())
add_col = AddColumn("lead_sources", col, if_not_exists=True)
compiled = str(add_col.compile(dialect=postgresql.dialect()))
print(f"Compiled DDL: {compiled}")
