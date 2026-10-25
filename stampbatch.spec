# PyInstaller spec — build with: pyinstaller stampbatch.spec
a = Analysis(['gui.py'], pathex=[], binaries=[],
             datas=[('assets/DejaVuSans.ttf', 'assets'),
                    ('assets/DejaVuSans-Bold.ttf', 'assets')],
             hiddenimports=[],
             hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='StampBatch',
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='StampBatch')
