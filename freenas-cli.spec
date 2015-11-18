# -*- mode: python -*-
import glob
import platform

block_cipher = None

def resource_path(relative_path):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

a = Analysis(['freenas/cli/repl.py'],
    pathex=['/home/william/scm/middleware/src/cli'],
    binaries=None,
    datas=None,
    hiddenimports=['freenas.cli.output.ascii', 'Queue'],
    hookspath=None,
    runtime_hooks=None,
    excludes=None,
    win_no_prefer_redirects=None,
    win_private_assemblies=None,
    cipher=block_cipher)

a.datas += [('freenas/cli/parser.py', resource_path('freenas/cli/parser.py'),  'DATA')]
for f in glob.glob('freenas/cli/plugins/*'):
    if not os.path.isfile(f):
        continue
    a.datas += [(f, resource_path(f),  'DATA')]

for f in glob.glob('freenas/cli/output/*'):
    if not os.path.isfile(f):
        continue
    a.datas += [(f, resource_path(f),  'DATA')]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if platform.system() == 'Windows':
    exe = EXE(pyz,
        a.binaries,
        a.datas,
        a.scripts,
        exclude_binaries=True,
        name='freenas-cli',
        debug=False,
        strip=None,
        upx=True,
        console=True )
elif platform.system() == 'Darwin':
    exe = EXE(pyz,
        a.scripts,
        exclude_binaries=True,
        name='freenas-cli',
        debug=False,
        strip=None,
        upx=True,
        console=True)
    app = BUNDLE(exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        name='freenas-cli.app',
        icon=None,
        bundle_identifier='org.freenas.cli')
