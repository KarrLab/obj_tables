""" Support for abstract model classes

:Author: Jonathan Karr <karr@mssm.edu>
:Date: 2017-05-23
:Copyright: 2016, Karr Lab
:License: MIT
"""

from __future__ import absolute_import
from abc import abstractmethod
import abc
import obj_tables.core
import six


class AbstractModelMeta(obj_tables.core.ModelMeta, abc.ABCMeta):
    """ Abstract model metaclass """
    pass


class AbstractModel(six.with_metaclass(AbstractModelMeta, obj_tables.core.Model)):
    """ Abstract model base class """
    pass
