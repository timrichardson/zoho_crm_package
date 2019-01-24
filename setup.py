from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

# https://pypi.org/classifiers/
setup(
        name='zoho_crm_connector',
        keywords='zoho crm',
        version='0.1.1',
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
        long_description=readme()
        )
