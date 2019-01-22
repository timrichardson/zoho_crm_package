from setuptools import setup

def readme():
    with open('README.rst') as f:
        return f.read()

# https://pypi.org/classifiers/
setup(
        name='zoho_crm',
        version='0.1.1',
        packages=['zoho_crm'],
        install_requires=['requests',
            ],
        setup_requires=["pytest-runner",],
        tests_require=["pytest",],
        classifiers=[
            'Development Status :: 2 - Pre-Alpha',
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3.7',
            'Topic :: Text Processing :: Linguistic',
            ],
        url='',
        license='GPL v3',
        author='Tim Richardson',
        author_email='tim@growthpath.com.au',
        description='Zoho CRM connector',
        long_description=readme()
        )
