from setuptools import setup, find_packages

setup(
    name="epwupgrader",
    version="0.1.0",
    description=(
        "Morph EnergyPlus Weather (EPW) files to future climate conditions "
        "using CMIP6 SSP5-8.5 anomaly data and the Belcher et al. (2005) "
        "morphing methodology."
    ),
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="epwupgrader contributors",
    python_requires=">=3.9",
    packages=find_packages(exclude=["tests*"]),
    install_requires=[
        "pandas>=1.3",
        "numpy>=1.21",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "flake8>=6.0",
            "black>=23.0",
        ],
        "full": [
            "xarray>=2022.0",
            "netCDF4>=1.6",
        ],
    },
    entry_points={
        "console_scripts": [
            "epwupgrader=epwupgrader.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
    ],
)