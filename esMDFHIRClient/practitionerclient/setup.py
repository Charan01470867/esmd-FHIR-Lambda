from setuptools import setup, find_packages

setup(
    name='practitionerclient',  # Name of your package
    version='0.1',  # Package version
    description='Practitioner Client to register providers for esMD services',
    author='Srini',
    author_email='srinivase@c-hit.com',
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
