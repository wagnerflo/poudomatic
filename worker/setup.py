from pathlib import Path
from setuptools import setup

setup(
    name="poudomatic-worker",
    description="Continuous packaging for FreeBSD: REST API and task runner.",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    version="0.1",
    author="Florian Wagner",
    author_email="florian@wagner-flo.net",
    url="https://github.com/wagnerflo/poudomatic",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: POSIX :: BSD :: FreeBSD",
        "Programming Language :: C",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: System :: Archiving :: Packaging",
        "Topic :: System :: Systems Administration",
    ],
    license_files=["../LICENSE"],
    python_requires=">=3.8",
    install_requires=[
        "fastapi",
        "GitPython",
        "sse-starlette",
    ],
    packages=[
        "poudomatic.worker",
    ],
)
