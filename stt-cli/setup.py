from setuptools import setup, find_packages

setup(
    name="stt-cli",
    version="0.1",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'stt=stt_client:main',
            'stt-server=start_stt_server:main',
        ],
    },
)