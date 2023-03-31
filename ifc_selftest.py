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
import Draft
import Arch
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

        FreeCAD.Console.PrintMessage("1.  NativeIFC import: Single object, coin mode...")
        clearObjects()
        fp = getIfcFilePath()
        ifc_import.insert(fp, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True)
        fco = len(FreeCAD.getDocument("IfcTest").Objects)
        self.failUnless(fco == 1, "ImportCoinSingle failed")


    def test02_ImportCoinStructure(self):

        FreeCAD.Console.PrintMessage("2.  NativeIFC import: Model structure, coin mode...")
        clearObjects()
        fp = getIfcFilePath()
        ifc_import.insert(fp, "IfcTest", strategy=1, shapemode=1, switchwb=0, silent=True)
        fco = len(FreeCAD.getDocument("IfcTest").Objects)
        self.failUnless(fco == 4, "ImportCoinStructure failed")


    def test03_ImportCoinFull(self):

        global FCSTD_FILE_PATH
        FreeCAD.Console.PrintMessage("3.  NativeIFC import: Full model, coin mode...")
        clearObjects()
        fp = getIfcFilePath()
        d = ifc_import.insert(fp, "IfcTest", strategy=2, shapemode=1, switchwb=0, silent=True)
        path = tempfile.mkstemp(suffix=".FCStd")[1]
        d.saveAs(path)
        FCSTD_FILE_PATH = path
        fco = len(FreeCAD.getDocument("IfcTest").Objects)
        self.failUnless(fco > 4, "ImportCoinFull failed")


    def test04_ImportShapeFull(self):

        FreeCAD.Console.PrintMessage("4.  NativeIFC import: Full model, shape mode...")
        clearObjects()
        fp = getIfcFilePath()
        d = ifc_import.insert(fp, "IfcTest", strategy=2, shapemode=0, switchwb=0, silent=True)
        fco = len(FreeCAD.getDocument("IfcTest").Objects)
        self.failUnless(fco > 4, "ImportShapeFull failed")


    def test05_ImportFreeCAD(self):

        FreeCAD.Console.PrintMessage("5.  FreeCAD import: NativeIFC coin file...")
        clearObjects()
        doc = FreeCAD.open(FCSTD_FILE_PATH)
        obj = doc.Objects[-1]
        proj = ifc_tools.get_project(obj)
        ifcfile = ifc_tools.get_ifcfile(proj)
        print(ifcfile)
        self.failUnless(ifcfile, "ImportFreeCAD failed")


    def test06_ModifyObjects(self):

        FreeCAD.Console.PrintMessage("6.  Modifying IFC document...")
        doc = FreeCAD.open(FCSTD_FILE_PATH)
        obj = doc.Objects[-1]
        obj.Label = obj.Label + "Modified"
        proj = ifc_tools.get_project(obj)
        proj.FilePath = proj.FilePath[:-4] + "_modified.ifc"
        ifc_tools.save_ifc(proj)
        ifc_diff = compare(IFC_FILE_PATH, proj.FilePath)
        obj.ShapeMode = 0
        obj.Proxy.execute(obj)
        self.failUnless(obj.Shape.Volume > 2 and len(ifc_diff) == 3, "ModifyObjects failed")


    def test07_CreateDocument(self):

        FreeCAD.Console.PrintMessage("7.  Creating new IFC document...")
        doc = FreeCAD.ActiveDocument
        ifc_tools.create_document(doc)
        fco = len(FreeCAD.getDocument("IfcTest").Objects)
        print(FreeCAD.getDocument("IfcTest").Objects[0])
        self.failUnless(fco == 1, "CreateDocument failed")


    def test08_ChangeIFCSchema(self):

        FreeCAD.Console.PrintMessage("8.  Changing IFC schema...")
        clearObjects()
        fp = getIfcFilePath()
        ifc_import.insert(fp, "IfcTest", strategy=2, shapemode=1, switchwb=0, silent=True)
        obj = FreeCAD.getDocument("IfcTest").Objects[-1]
        proj = ifc_tools.get_project(obj)
        oldid = obj.StepId
        proj.Proxy.silent = True
        proj.Schema = "IFC2X3"
        FreeCAD.getDocument("IfcTest").recompute()
        self.failUnless(obj.StepId != oldid, "ChangeIFCSchema failed")


    def test09_CreateBIMObjects(self):

        FreeCAD.Console.PrintMessage("9.  Creating BIM objects...")
        doc = FreeCAD.ActiveDocument
        proj = ifc_tools.create_document(doc)
        site = Arch.makeSite()
        site = ifc_tools.aggregate(site, proj)
        bldg = Arch.makeBuilding()
        bldg = ifc_tools.aggregate(bldg, site)
        storey = Arch.makeFloor()
        storey = ifc_tools.aggregate(storey, bldg)
        wall = Arch.makeWall(None, 200, 400,20)
        wall = ifc_tools.aggregate(wall, storey)
        column = Arch.makeStructure(None, 20, 20, 200)
        column.IfcType = "Column"
        column = ifc_tools.aggregate(column, storey)
        beam = Arch.makeStructure(None, 20, 200, 20)
        beam.IfcType = "Beam"
        beam = ifc_tools.aggregate(beam, storey)
        rect = Draft.makeRectangle(200, 200)
        slab = Arch.makeStructure(rect, height=20)
        slab.IfcType = "Slab"
        slab = ifc_tools.aggregate(slab, storey)
        # TODO create door, window
        fco = len(FreeCAD.getDocument("IfcTest").Objects)
        ifco = len(proj.Proxy.ifcfile.by_type("IfcRoot"))
        print(ifco, "IFC objects created")
        self.failUnless(fco == 8 and ifco == 12, "CreateDocument failed")

# test remove object


