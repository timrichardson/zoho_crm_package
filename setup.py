from setuptools import setup
from sphinx.setup_command import BuildDoc
cmdclass = {'build_sphinx': BuildDoc}

def readme():
    with open('README.rst') as f:
        return f.read()

# https://pypi.org/classifiers/

name='zoho_crm_connector'
keywords='zoho crm'
version='0.2.0'

setup(
        name=name,
        keywords=keywords,
        version=version,
        packages=['zoho_crm_connector'],
        python_requires='>=3.6',
        install_requires=['requests',
            ],
        setup_requires=["pytest-runner",],
        tests_require=["pytest",],
        classifiers=[
            'Development Status :: 3 - Alpha',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3.7',
            'Topic :: Text Processing :: Linguistic',
            ],
        url='https://github.com/timrichardson/zoho_crm_package',
        license='GPL v3',
        author='Tim Richardson',
        author_email='tim@growthpath.com.au',
        description='Zoho CRM connector',
        long_description=readme(),
     cmdclass=cmdclass,
        # these are optional and override conf.py settings
        command_options={
            'build_sphinx': {
                'project': ('setup.py', name),
                'version': ('setup.py', version),
                'release': ('setup.py', version),
                'source_dir': ('setup.py', 'docs')}},

        )
