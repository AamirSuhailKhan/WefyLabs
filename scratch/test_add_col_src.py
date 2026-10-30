import inspect
from alembic.ddl.impl import DefaultImpl
from alembic.ddl import base

print(inspect.getsource(DefaultImpl.add_column))
