This wc_lang directory contains contains a copy of wc_lang/core.py that's used to unittest migrate.py, especially the migration of data based on wc_lang schemas. The file core_modified.py contains a slightly modified copy of wc_lang/core.py.

Directories and sub-modules of wc_lang that aren't used when wc_lang/core.py is imported as a schema have been removed to simplify and shrink this directory.

These test files will need to be updated as wc_lang/core.py and its dependencies change.

Procedure to update this fixture:

    1. Obtain the current version of wc_lang from github.com/KarrLab/wc_lang
    2. Copy the current wc_lang/core.py to wc_lang_fixture/wc_lang/core.py
    3. In wc_lang_fixture/wc_lang:
        a. copy core.py to core_modified.py
        b. in core_modified.py, replace 'Parameter' with 'ParameterRenamed'
        c. optionally replace 'libsbml.ParameterRenamed' with 'libsbml.Parameter', that are only in comments
    4. Run the unittests for migration:
        pytest -s tests/test_migrate.py

    If this does not work, then
        1. Copy all of wc_lang/* to wc_lang_fixture/
        2. Remove unnecessary files and directories from wc_lang_fixture/wc_lang
        3. Do steps 3. and 4. above