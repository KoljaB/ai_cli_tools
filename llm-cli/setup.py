from setuptools import setup, find_packages

setup(
    name="llm-cli",
    version="0.1",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'llm=llm:main',
            'llm-server=start_llm_server:main',
        ],
    },
)