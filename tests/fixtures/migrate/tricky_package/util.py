# why doesn't this reproduce the cyclic import error in wc_lang_33075c4/wc_lang/core.py?
import traceback

print('\nin tricky_package/another.py:')
traceback.print_stack(limit=20)

from obj_model import get_models as base_get_models
from tricky_package import test_module
from tricky_package import io