set python="C:\Python2.7\python.exe"
set pip=".\venv\Scripts\pip.exe"

%python% -m virtualenv venv
%pip% install -U https://github.com/pyinstaller/pyinstaller/archive/develop.zip
%pip% install freenas.cli
.\venv\Scripts\pyinstaller -y --clean --onefile freenas-cli.spec
