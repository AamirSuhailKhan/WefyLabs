import alembic
from alembic.ddl.impl import DefaultImpl
from alembic.ddl.postgresql import PostgresqlImpl
from alembic.operations import ops
import sqlalchemy as sa

print("Checking PostgresqlImpl in Alembic...")
print(dir(PostgresqlImpl))
