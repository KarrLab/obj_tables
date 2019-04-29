""" Test VirtualEnvUtil

:Author: Arthur Goldberg <Arthur.Goldberg@mssm.edu>
:Date: 2019-04-29
:Copyright: 2019, Karr Lab
:License: MIT
"""

# todo
# add virtualenvapi to reqs

import unittest
import os
import socket
from tempfile import mkdtemp
import shutil
import time

from obj_model.virtualenv_utils import VirtualEnvUtil
from virtualenvapi.manage import VirtualEnvironment

# todo: move to wc_utils
def internet_connected():
    # return True if the internet (actually www.google.com) is connected, false otherwise
    try:
        # connect to the host -- tells us if the host is actually reachable
        socket.create_connection(("www.google.com", 80))
        return True
    except OSError:
        pass
    return False


@unittest.skipUnless(internet_connected(), "Internet not connected")
class TestVirtualEnvUtil(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = mkdtemp()
        self.test_virt_env_util = VirtualEnvUtil('test', dir=self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_init(self):
        virt_env_util_1 = VirtualEnvUtil('test_name')
        virt_env_util_2 = VirtualEnvUtil('test_name', dir=self.tmp_dir)
        for virt_env_util in [virt_env_util_1, virt_env_util_2]:
            self.assertEqual(virt_env_util.name, 'test_name')
            self.assertTrue(os.path.isdir(virt_env_util.virtualenv_dir))
            self.assertTrue(isinstance(virt_env_util.env, VirtualEnvironment))

        with self.assertRaisesRegex(ValueError, "name '.*' may not contain whitespace"):
            VirtualEnvUtil('name with\twhitespace')

    def test_is_installed(self):
        pass

    def run_and_check_install(self, pip_spec, package):
        print('installing', pip_spec, end='')
        # todo: get & reuse parser for pip specs
        start = time.time()
        self.test_virt_env_util.install_from_pip_spec(pip_spec)
        duration = time.time() - start
        print(" took {0:.1f} sec".format(duration))
        # print(self.test_virt_env_util.env.installed_packages)
        self.assertTrue(self.test_virt_env_util.is_installed(package))
        # todo: check that the package has the right version (esp. if hash specified) & can be used

    def test_install_from_pip_spec(self):
        # test PyPI package
        self.run_and_check_install('six', 'six')
        # test PyPI package with version
        self.run_and_check_install('django==1.4', 'django')
        # test WC egg
        self.run_and_check_install('git+https://github.com/KarrLab/log.git#egg=log', 'log')
        # test WC URL commit specified by hash
        self.run_and_check_install(
            'git+git://github.com/KarrLab/wc_onto.git@ced0ba452bbdf332c9f687b78c2fedc68c666ff2', 'wc-onto')
        # test wc_lang commit
        self.run_and_check_install(
            'git+git://github.com/KarrLab/wc_lang.git@6f1d13ea4bafac443a4fcee3e97a85874fd6bd04', 'wc-lang')
        # as of 4/19, https://pip.pypa.io/en/latest/reference/pip_install/#git describes pip package spec. forms for git
        # todo: try other forms

    def test_install_from_pip_spec_exception(self):
        pass

    def test_destroy_and_destroyed(self):
        virt_env_util = VirtualEnvUtil('test_name')
        self.assertTrue(os.path.isdir(virt_env_util.virtualenv_dir))
        virt_env_util.destroy()
        self.assertFalse(os.path.isdir(virt_env_util.virtualenv_dir))
        self.assertTrue(virt_env_util.destroyed())

    def test_(self):
        pass
