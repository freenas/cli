set python="C:\Python27\python.exe"
set pip=".\venv\Scripts\pip.exe"

%python% -m virtualenv venv
%pip% install -U https://github.com/pyinstaller/pyinstaller/archive/develop.zip
%pip% install -U freenas.cli
.\venv\Scripts\pyinstaller -y --clean --onefile freenas-cli.spec
