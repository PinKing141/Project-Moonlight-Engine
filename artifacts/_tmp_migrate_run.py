import os
from pathlib import Path

os.environ['RPG_DATABASE_URL'] = "mysql+mysqlconnector://root:password123@localhost:3306/moonlight_rpg"

from rpg.infrastructure.db.mysql.migrate import build_migration_plan, execute_statements

plan = build_migration_plan()
print('plan_files', len(plan.files), 'plan_statements', len(plan.statements), flush=True)
count = execute_statements(plan.statements, os.environ['RPG_DATABASE_URL'])
print('executed', count, flush=True)
