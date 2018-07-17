import subprocess

from setuptools import setup, find_packages

setup(
    name='sawtooth_battleship',
    version=subprocess.check_output(
        ['../../../bin/get_version']).decode('utf-8').strip(),
    description='Sawtooth Battleship',
    author='Hyperledger Sawtooth',
    url='https://github.com/hyperledger/sawtooth-core',
    packages=find_packages(),
    install_requires=[
        'colorlog',
        'sawtooth-sdk',
        'sawtooth-signing',
    ],
    entry_points={
        'console_scripts': [
            'battleship-cli-python = sawtooth_battleship.battleship_cli:main_wrapper',
        ]
    }
)
