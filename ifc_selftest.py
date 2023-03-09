#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2023 Yorik van Havre <yorik@uncreated.net>              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU General Public License (GPL)            *
#*   as published by the Free Software Foundation; either version 3 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU General Public License for more details.                          *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

import os
import time
import tempfile
import FreeCAD
import unittest
import requests
import ifc_import
import ifc_tools
import difflib

IFCOPENHOUSE_IFC4 = "https://github.com/aothms/IfcOpenHouse/raw/master/IfcOpenHouse_IFC4.ifc"
IFC_FILE_PATH = None # downloaded IFC file path
FCSTD_FILE_PATH = None # saved FreeCAD file


"""
unit tests for the NativeIFC functionality. To run the tests, either:
- in terminal mode: FreeCAD -t ifc_selftest
- in the FreeCAD UI: Switch to Test Framework workbench, press "Self test" and choose ifc_selftest in the list
"""


def getIfcFilePath():

    global IFC_FILE_PATH
    if not IFC_FILE_PATH:
        path = tempfile.mkstemp(suffix=".ifc")[1]
        results = requests.get(IFCOPENHOUSE_IFC4)
        with open(path, 'wb') as f:
            f.write(results.content)
        IFC_FILE_PATH = path
    return IFC_FILE_PATH


def clearObjects():

    names = [o.Name for o in FreeCAD.getDocument("IfcTest").Objects]
    for n in names:
        FreeCAD.getDocument("IfcTest").removeObject(n)


def compare(file1, file2):

    with open(file1) as f1:
        f1_text = f1.readlines()
    with open(file2) as f2:
        f2_text = f2.readlines()
    res = [l for l in difflib.unified_diff(f1_text, f2_text, fromfile=file1, tofile=file2, lineterm='')]
    res = [l for l in res if l.startswith("+") or l.startswith("-")]
    res = [l for l in res if not l.startswith("+++") and not l.startswith("---")]
    return res


class ArchTest(unittest.TestCase):

    def setUp(self):

        # setting a new document to hold the tests
        if FreeCAD.ActiveDocument:
            if FreeCAD.ActiveDocument.Name != "IfcTest":
                FreeCAD.newDocument("IfcTest")
        else:
            FreeCAD.newDocument("IfcTest")
        FreeCAD.setActiveDocument("IfcTest")


    def tearDown(self):

        FreeCAD.closeDocument("IfcTest")
        pass


    def test01_ImportCoinSingle(self):

        FreeCAD.Console.PrintMessage("NativeIFC import: Single object, coin mode...")
        clearObjects()
        fp = getIfcFilePath()
        ifc_import.insert(fp, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True)
        self.failUnless(len(FreeCAD.getDocument("IfcTest").Objects) == 1, "ImportCoinSingle failed")


    def test02_ImportCoinStructure(self):

        FreeCAD.Console.PrintMessage("NativeIFC import: Model structure, coin mode...")
        clearObjects()
        fp = getIfcFilePath()
        ifc_import.insert(fp, "IfcTest", strategy=1, shapemode=1, switchwb=0, silent=True)
        self.failUnless(len(FreeCAD.getDocument("IfcTest").Objects) == 4, "ImportCoinStructure failed")


    def test03_ImportCoinFull(self):

        global FCSTD_FILE_PATH
        FreeCAD.Console.PrintMessage("NativeIFC import: Full model, coin mode...")
        clearObjects()
        fp = getIfcFilePath()
        d = ifc_import.insert(fp, "IfcTest", strategy=2, shapemode=1, switchwb=0, silent=True)
        path = tempfile.mkstemp(suffix=".FCStd")[1]
        d.saveAs(path)
        FCSTD_FILE_PATH = path
        self.failUnless(len(FreeCAD.getDocument("IfcTest").Objects) > 4, "ImportCoinFull failed")


    def test04_ImportShapeFull(self):

        FreeCAD.Console.PrintMessage("NativeIFC import: Full model, coin mode...")
        clearObjects()
        fp = getIfcFilePath()
        d = ifc_import.insert(fp, "IfcTest", strategy=2, shapemode=0, switchwb=0, silent=True)
        self.failUnless(len(FreeCAD.getDocument("IfcTest").Objects) > 4, "ImportShapeFull failed")


    def test05_ImportFreeCAD(self):

        FreeCAD.Console.PrintMessage("FreeCAD import: NativeIFC coin file...")
        clearObjects()
        doc = FreeCAD.open(FCSTD_FILE_PATH)
        obj = doc.Objects[-1]
        proj = ifc_tools.get_project(obj)
        ifcfile = ifc_tools.get_ifcfile(proj)
        self.failUnless(ifcfile, "ImportFreeCAD failed")


    def test06_ModifyObjects(self):

        doc = FreeCAD.open(FCSTD_FILE_PATH)
        obj = doc.Objects[-1]
        obj.Label = obj.Label + "Modified"
        proj = ifc_tools.get_project(obj)
        proj.FilePath = proj.FilePath + "modified.ifc"
        ifc_tools.save_ifc(proj)
        ifc_diff = compare(IFC_FILE_PATH, proj.FilePath)
        obj.ShapeMode = 0
        obj.Proxy.execute(obj)
        self.failUnless(obj.Shape.Volume > 2 and len(ifc_diff) == 3, "ModifyObjects failed")

