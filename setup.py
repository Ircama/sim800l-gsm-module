#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#############################################################################
# Driver for SIM800L module (using AT commands)
# Tested on Raspberry Pi
#############################################################################

from setuptools import setup, find_packages
import re
import os
import sys

import json
from urllib import request
from pkg_resources import parse_version

###########################################################################

END_OF_INTRODUCTION = '### Installation'

EPILOGUE = '''
Full information, installation notes, API reference and usage details at the [sim800l-gsm-module GitHub repository](https://github.com/Ircama/raspberry-pi-sim800l-gsm-module).
'''

DESCRIPTION = ("Raspberry Pi SIM800L GSM module")

PACKAGE_NAME = "sim800l-gsm-module"

VERSIONFILE = "sim800l/__version__.py"

###########################################################################

def versions(pkg_name, site):
    url = 'https://' + site + '.python.org/pypi/' + pkg_name + '/json'
    print("Package " + pkg_name + ". Site URL: " + url)
    try:
        releases = json.loads(request.urlopen(url).read())['releases']
    except Exception as e:
        print("Error while getting data from URL '" + url + "': " + repr(e))
        return []
    return sorted(releases, key=parse_version, reverse=True)

with open("README.md", "r") as readme:
    long_description = readme.read()

build = ''
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

if os.environ.get('GITHUB_RUN_NUMBER') is not None:
    version_list_pypi = [
        a for a in versions(PACKAGE_NAME, 'pypi') if a.startswith(verstr)]
    version_list_testpypi = [
        a for a in versions(PACKAGE_NAME, 'testpypi') if a.startswith(verstr)]
    if (version_list_pypi or
            version_list_testpypi or
            os.environ.get('GITHUB_FORCE_RUN_NUMBER') is not None):
        print('---------------------------------'
            '---------------------------------')
        print("Using build number " + os.environ['GITHUB_RUN_NUMBER'])
        if version_list_pypi:
            print(
                "Version list available in pypi: " +
                ', '.join(version_list_pypi))
        if version_list_testpypi:
            print(
                "Version list available in testpypi: " +
                ', '.join(version_list_testpypi))
        print('---------------------------------'
            '---------------------------------')
        verstr += '-' + os.environ['GITHUB_RUN_NUMBER']

setup(
    name=PACKAGE_NAME,
    version=verstr,
    description=(DESCRIPTION),
    long_description=long_description[
        :long_description.find(END_OF_INTRODUCTION)] + EPILOGUE,
    long_description_content_type="text/markdown",
    classifiers=[
        "Operating System :: POSIX :: Linux",
        "License :: Other/Proprietary License",
        "Topic :: Communications",
        "Topic :: Software Development :: Libraries :: Python Modules",
        'Programming Language :: Python :: 3 :: Only',
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Telecommunications Industry",
        "Intended Audience :: Developers",
    ],
    keywords=("Raspberry Pi SIM800L GSM module"),
    author="Ircama",
    url="https://github.com/Ircama/raspberry-pi-sim800l-gsm-module",
    license='CC-BY-NC-SA-4.0',
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'pyserial',
        'gsm0338'
    ],
    python_requires='>3.5'
)
