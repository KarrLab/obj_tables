""" Migration to new ObjTables format

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2019-10-10
:Copyright: 2019, Karr Lab
:License: MIT
"""

import glob
import sys

sys.path.insert(0, 'migrations')
import migration_2020_03_09 as migration

for filename in glob.glob('**/*.xlsx', recursive=True):
    print('Migrating {}'.format(filename))
    migration.transform(filename)
