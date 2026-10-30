import inspect
from alembic.ddl.postgresql import PostgresqlImpl

print(inspect.getsource(PostgresqlImpl.create_index))
