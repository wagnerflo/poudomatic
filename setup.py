from pathlib import Path
from setuptools import setup,Extension
from subprocess import check_output

def pkgconfig(*args):
    return check_output(('pkg-config',) + args, text=True).strip().split()

setup(
    name='poudomatic',
    description='Continuous packaging for FreeBSD.',
    long_description=(Path(__file__).parent / 'README.md').read_text(),
    long_description_content_type='text/markdown',
    version='0.1',
    author='Florian Wagner',
    author_email='florian@wagner-flo.net',
    url='https://github.com/wagnerflo/poudomatic',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: BSD :: FreeBSD',
        'Programming Language :: C',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Archiving :: Packaging',
        'Topic :: System :: Systems Administration',
    ],
    license_files=['LICENSE'],
    python_requires='>=3.8',
    install_requires=[
        'fasteners',
        'GitPython',
        'Jinja2',
        'pkgdiff',
        'yamap',
    ],
    ext_modules=[
        Extension(
            'poudomatic.libpkg',
            sources=['poudomatic/libpkg.c'],
            extra_compile_args=[*pkgconfig('--cflags', 'pkg')],
            extra_link_args=[*pkgconfig('--libs', 'pkg')],
        ),
    ],
    packages=[
        'poudomatic',
    ],
    entry_points={
        'console_scripts': [
            'poudomatic = poudomatic.cmdline:main',
        ],
    },
)
