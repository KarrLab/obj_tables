""" Support for abstract model classes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from abc import abstractmethod  # noqa: F401
import abc
import obj_tables.core


class AbstractModelMeta(obj_tables.core.ModelMeta, abc.ABCMeta):
    """ Abstract model metaclass """
    pass


class AbstractModel(obj_tables.core.Model, metaclass=AbstractModelMeta):
    """ Abstract model base class """
    pass
