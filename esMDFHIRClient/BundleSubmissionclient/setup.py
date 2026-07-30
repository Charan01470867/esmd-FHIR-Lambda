from setuptools import setup, find_packages

setup(
    name='bundlesubmissionclient',  # Name of your package
    version='0.1',  # Package version
    description='esMD Bundle Submission Client',
    author='Srini',
    author_email='sai@digitalhie.com',
    url='',  # Project URL (optional)
    packages=find_packages(),  # Automatically find packages in the directory
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.9',  # Minimum Python version required
    install_requires=[ 'flask', 'requests', 'fhirclient', 'twilio', 'pika', 'pandas', 'oauthlib', 'schedule', 'pyyaml', 'apscheduler' ],
)
