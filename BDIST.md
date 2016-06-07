Windows
-------

Notes about building exe bundle for Windows.

This is going to generate a single .exe file being able to run the freenas-cli program.

Requirements
++++++++++++

- Python 2.7 (Preferably in C:\Python2.7)
- pip
- virtualenv
- Visual C++ For Python 2.7 (to build pycrypto)

Build
+++++

Simply run the setup.bat file from this directory.

> setup.bat

freenas-cli.exe should now be available under dist/.


Mac OS X
--------

Notes about building .app container for Mac OS X.

Requirements
++++++++++++

- Python 2.7 (Preferably in C:\Python2.7)
- pip
- virtualenv

## Setup environment (Mac)
You will need python (>3.4), pip and virtualenv to get your environment setup.  

1. install macports [mac ports installer](https://www.macports.org/install.php)
2. install python3.4
  * sudo port install python34
3. install pip
	* sudo port install py34-pip
4. set active versions of python and pip
	OSX comes with Python2.7 pre-installed.  Use port to select your active version.
	* sudo port select --set python python34
	* sudo port select --set pip pip34
5. use pip to install virtualenv and create symlink if needed (used for build process...docs not complete yet for that...)
	* sudo pip install virtualenv
	* sudo ln -s /usr/local/bin/virtualenv /usr/local/bin/virtualenv-3.4
6. install module dependencies for running cli
	* sudo pip install six paramiko python-dateutil ply jsonschema ws4py gnureadline natural texttable columnize
7. set python path for cli
	* export set PYTHONPATH=../dispatcher/client/python/:../utils
8. change into cli directory and run FreeNAS cli
	* python -m freenas.cli.repl

You should be off to the races at this point.  These docs are a work in progress so please excuse any flaws or omissions.



Build
+++++

Simply run the make bin from this directory.

$ make bin

freenas-cli.app should be available under dist/.


Signing
+++++++

The app bundle needs to be signed

$ codesign -s "Cert Name" --deep freenas-cli.app

For more information: https://github.com/pyinstaller/pyinstaller/wiki/Recipe-OSX-Code-Signing
