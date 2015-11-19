Windows
-------

Notes about building exe bundle for Windows.

This is going to generate a single .exe file being able to run the freenas-cli program.

Requirements
++++++++++++

- Python 2.7 (Preferably in C:\Python2.7)
- pip
- virtualenv

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
