import importlib.util
import json
import plistlib
import struct
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "apple-bridge"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

inspect = None
report_mod = None


def macho64(cputype=0x01000007, deps=()):
    cmds=[]
    for dep in deps:
        raw=dep.encode()+b'\0'
        size=((24+len(raw)+7)//8)*8
        cmd=struct.pack('<IIIIII',0x0c,size,24,0,0,0)+raw
        cmd += b'\0'*(size-len(cmd))
        cmds.append(cmd)
    header=struct.pack('<IiiIIIII',0xfeedfacf,cputype,3,2,len(cmds),sum(map(len,cmds)),0,0)
    return header+b''.join(cmds)

class AppleBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global inspect, report_mod
        inspect=load('inspect_macho', BRIDGE/'inspect_macho.py')
        report_mod=load('compatibility_report', BRIDGE/'compatibility_report.py')

    def test_parses_x86_64_macho_and_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'tool'
            p.write_bytes(macho64(deps=['/usr/lib/libSystem.B.dylib']))
            r=inspect.inspect_macho(p)
            self.assertTrue(r['valid'])
            self.assertEqual(r['architecture'],'x86_64')
            self.assertEqual(r['bits'],64)
            self.assertIn('/usr/lib/libSystem.B.dylib',r['dependencies'])

    def test_rejects_arm64_for_intel_bridge(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'tool'; p.write_bytes(macho64(cputype=0x0100000c))
            r=inspect.inspect_macho(p)
            self.assertEqual(r['architecture'],'arm64')

    def test_malformed_binary_is_not_valid(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad'; p.write_bytes(b'not macho')
            r=inspect.inspect_macho(p)
            self.assertFalse(r['valid'])

    def test_resolves_bundle_executable_and_reports_missing_framework(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td)/'Demo.app'; macos=app/'Contents'/'MacOS'; macos.mkdir(parents=True)
            (app/'Contents'/'Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable':'Demo'}))
            exe=macos/'Demo'; exe.write_bytes(macho64(deps=['/System/Library/Frameworks/AppKit.framework/Versions/C/AppKit']))
            result=report_mod.compatibility_report(app, available_dependencies=set())
            self.assertEqual(result['executable_path'],str(exe))
            self.assertEqual(result['classification'],'unsupported')
            self.assertTrue(result['missing_dependencies'])

    def test_x86_64_macho_without_missing_deps_is_experimental(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td)/'Tiny.app'; macos=app/'Contents'/'MacOS'; macos.mkdir(parents=True)
            (app/'Contents'/'Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable':'Tiny'}))
            (macos/'Tiny').write_bytes(macho64())
            result=report_mod.compatibility_report(app, available_dependencies=set())
            self.assertEqual(result['classification'],'experimental')

    def test_native_script_bundle_is_native_tool(self):
        with tempfile.TemporaryDirectory() as td:
            app=Path(td)/'Script.app'; macos=app/'Contents'/'MacOS'; macos.mkdir(parents=True)
            (app/'Contents'/'Info.plist').write_bytes(plistlib.dumps({'CFBundleExecutable':'run'}))
            exe=macos/'run'; exe.write_text('#!/bin/sh\nexit 0\n'); exe.chmod(0o755)
            result=report_mod.compatibility_report(app, available_dependencies=set())
            self.assertEqual(result['classification'],'native-tool')

if __name__ == '__main__': unittest.main()
