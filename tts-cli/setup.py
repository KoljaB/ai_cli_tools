from setuptools import setup, find_packages

setup(
    name="tts-cli",
    version="0.1",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'tts=tts:main',
            'tts-server=start_tts_server:main',            
        ],
    },
)