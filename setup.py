import setuptools
try:
    import pkg_utils
except ImportError:
    import pip._internal
    pip._internal.main(['install', 'pkg_utils'])
    import pkg_utils
import os

name = 'obj_tables'
dirname = os.path.dirname(__file__)
package_data = {
    name: [
        'VERSION',
        'web_app/app.css',
        'web_app/app.js',
        'web_app/index.html',
    ],
}

# get package metadata
md = pkg_utils.get_package_metadata(dirname, name)

# install package
setuptools.setup(
    name=name,
    version=md.version,

    description='Database-independent Django-like object model',
    long_description=md.long_description,

    # The project's main homepage.
    url='https://github.com/KarrLab/' + name,
    download_url='https://github.com/KarrLab/' + name,

    author='Karr Lab',
    author_email='info@karrlab.org',

    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Developers',
        'Topic :: Database :: Database Engines/Servers',
        'Topic :: Software Development :: Object Brokering',
        'Topic :: Software Development :: Libraries :: Python Modules',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='object model, schema',

    packages=setuptools.find_packages(exclude=['tests', 'tests.*']),
    package_data=package_data,

    entry_points={
        'console_scripts': [
            'obj-tables = obj_tables.__main__:main',
        ],
    },

    install_requires=md.install_requires,
    extras_require=md.extras_require,
    tests_require=md.tests_require,
    dependency_links=md.dependency_links,
)
