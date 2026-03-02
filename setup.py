from setuptools import setup, find_packages

setup(
    name="lol-genius",
    version="0.1.0",
    packages=find_packages(),
    install_requires=open("requirements.txt").read().splitlines(),
    extras_require={
        "test": ["pytest>=8.0", "pytest-cov>=5.0"],
    },
    entry_points={
        "console_scripts": [
            "lol-genius=lol_genius.cli:cli",
            "lol-genius-proxy=lol_genius.proxy.run:main",
        ]
    },
    python_requires=">=3.11",
)
