from importlib.metadata import entry_points
from setuptools import setup

requirements = []
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name='ClashRoyaleManager',
    version='0.0.0',
    install_requires=requirements,
    packages=[
        'ClashRoyaleManager',
        'cogs',
        'config',
        'groups',
        'utils',
    ],
    entry_points={
        'console_scripts': [
            'ClashRoyaleManager = ClashRoyaleManager.__main__:main'
        ]
    }
)