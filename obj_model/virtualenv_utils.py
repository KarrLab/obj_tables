""" Create, use and destroy virtual environments for Python packages

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2019-04-29
:Copyright: 2019, Karr Lab
:License: MIT
"""

from tempfile import mkdtemp
import shutil
import os
import sys
import re
from virtualenvapi.manage import VirtualEnvironment
import virtualenvapi


class VirtualEnvUtil(object):
    """ Support creation, use and distruction of virtual environments for Python packages

    Attributes:
    """

    def __init__(self, name, dir=None):
        """ Initialize a `VirtualEnvUtil`

        Args:
            name (:obj:`str`): name for the `VirtualEnvUtil`
            dir (:obj:`str`, optional): a directory to hold the `VirtualEnvUtil`
        """
        if re.search('\s', name):
            raise ValueError("name '{}' may not contain whitespace".format(name))
        self.name = name
        if dir is None:
            dir = mkdtemp()
        self.virtualenv_dir = os.path.join(dir, name)
        os.mkdir(self.virtualenv_dir)
        self.env = VirtualEnvironment(self.virtualenv_dir)

    def is_installed(self, pip_spec):
        return self.env.is_installed(pip_spec)

    def install_from_pip_spec(self, pip_spec):
        """ Install a package from a `pip` specification

        Args:
            pip_spec (:obj:`str`): a `pip` specification for a package to load

        Raises:
            :obj:`ValueError`: if the package described by `pip_spec` cannot be installed
        """
        try:
            self.env.install(pip_spec)
        except virtualenvapi.exceptions.PackageInstallationException as e:
            print('returncode', e.returncode)
            print('output', e.output)
            print('package', e.package)

    def activate(self):
        """ Use this `VirtualEnvUtil`
        """
        # put the env on sys.path
        pass

    def deactivate(self):
        """ Stop using this `VirtualEnvUtil`
        """
        # remove this env from sys.path
        pass

    def destroy(self):
        """ Destroy this `VirtualEnvUtil`

        Distruction deletes the directory storing the `VirtualEnvUtil`
        """
        shutil.rmtree(self.virtualenv_dir)
        
    def destroyed(self):
        """ Test whether this `VirtualEnvUtil` has been destroyed
        """
        return not os.path.isdir(self.virtualenv_dir)
