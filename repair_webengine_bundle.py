"""Repair Qt WebEngine's split framework resources in a PyInstaller Mac bundle."""
from pathlib import Path
import os,shutil,subprocess
def repair_mac_bundle(bundle):
    frameworks=Path(bundle)/'Contents'/'Frameworks'
    resources=frameworks/'QtWebEngineCore.framework'
    actual=frameworks/'PySide6'/'Qt'/'lib'/'QtWebEngineCore.framework'
    if resources.exists() and not resources.is_symlink() and actual.exists():
        shutil.copytree(resources/'Versions'/'A',actual/'Versions'/'A',dirs_exist_ok=True,symlinks=True)
        shutil.rmtree(resources)
        resources.symlink_to(os.path.relpath(actual,frameworks),target_is_directory=True)
    helper_link=actual/'Helpers'
    if not helper_link.exists():helper_link.symlink_to('Versions/Current/Helpers',target_is_directory=True)
    helper=actual/'Helpers'/'QtWebEngineProcess.app'/'Contents'/'MacOS'/'QtWebEngineProcess'
    if not helper.is_file():raise RuntimeError('The packaged Qt WebEngine helper is missing.')
    rpath='@loader_path/'+os.path.relpath(frameworks.resolve(),helper.resolve().parent)
    load_commands=subprocess.run(['otool','-l',str(helper)],capture_output=True,text=True,check=True).stdout
    if rpath not in load_commands:subprocess.run(['install_name_tool','-add_rpath',rpath,str(helper)],check=True)
    subprocess.run(['codesign','--force','--deep','--sign','-',str(bundle)],check=True)
    subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
