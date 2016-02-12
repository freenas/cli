# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################
import platform
import sys
import os
import glob
from setuptools import setup, find_packages

example_files = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'freenas/cli/examples/*')

dependency_links = []
install_requires = [
    'freenas.utils',
    'freenas.dispatcher',
    'columnize',
    'ply',
    'termcolor',
    'texttable',
    'six',
    'pyte',
    'future',
    'natural>=0.1.6',
]

if sys.version_info.major == 3:
    if sys.version_info.minor < 4:
        install_requires.append('enum34')
    if sys.version_info.minor < 3:
        install_requires.append('backports.shutil_get_terminal_size')
else:
    install_requires.extend([
        'enum34',
        'backports.shutil_get_terminal_size',
    ])

if platform.system() == 'Darwin':
    install_requires.append('gnureadline')
elif platform.system() == 'Windows':
    install_requires.append('pyreadline')


setup(
    name='freenas.cli',
    url='http://github.com/freenas/middleware',
    packages=find_packages() + ['freenas.cli.plugins'],
    license='BSD',
    description='Command Line Interface for FreeNAS',
    platforms='any',
    namespace_packages=[str('freenas')],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
    ],
    install_requires=install_requires,
    dependency_links=dependency_links,
    entry_points={
        'console_scripts': [
            'freenas-cli = freenas.cli.repl:main',
        ],
    },
    setup_requires=['freenas.utils', 'six', 'ply'],
    data_files=[('freenas/cli/examples', [f for f in glob.glob(example_files)])],
    use_freenas=True,
)

# Generate parser
try:
    from freenas.cli import parser
except ImportError as err:
    raise err