""" Migration to new ObjTables format

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2020-04-27
:Copyright: 2020, Karr Lab
:License: MIT
"""

import glob
import sys

sys.path.insert(0, 'migrations')
import migration_2020_04_27 as migration  # noqa: E402

for filename in glob.glob('**/*.xlsx', recursive=True):
    print('Migrating {}'.format(filename))
    migration.transform(filename)
