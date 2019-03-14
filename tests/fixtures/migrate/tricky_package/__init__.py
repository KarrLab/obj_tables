import pkg_resources

with open(pkg_resources.resource_filename('tricky_package', 'VERSION'), 'r') as file:
    __version__ = file.read().strip()

from .test_module import Test, Reference
from . import io