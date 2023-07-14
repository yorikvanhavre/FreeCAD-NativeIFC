# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2023 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License (GPL)            *
# *   as published by the Free Software Foundation; either version 3 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU General Public License for more details.                          *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import os
import FreeCAD
import unittest
import ifc_import


FILES = [
    "IfcOpenHouse_IFC4.ifc",
    "FZK_haus.ifc",
    "schultz_residence.ifc",
    "nineteen_plots.ifc",
    "schependomlaan.ifc",
    "king_arch.ifc",
    "king_arch_full.ifc",
]


class NativeIFCTest(unittest.TestCase):
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

    def test01_IfcOpenHouse_coin(self):
        print("COIN MODE")
        f = FILES[0]
        ifc_import.insert(
            f, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True
        )
        self.failUnless(True, "import failed")

    def test02_IfcOpenHouse_coin(self):
        f = FILES[1]
        ifc_import.insert(
            f, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True
        )
        self.failUnless(True, "import failed")

    def test03_IfcOpenHouse_coin(self):
        f = FILES[2]
        ifc_import.insert(
            f, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True
        )
        self.failUnless(True, "import failed")

    def test04_IfcOpenHouse_coin(self):
        f = FILES[3]
        ifc_import.insert(
            f, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True
        )
        self.failUnless(True, "import failed")

    def test05_IfcOpenHouse_coin(self):
        f = FILES[4]
        ifc_import.insert(
            f, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True
        )
        self.failUnless(True, "import failed")

    def test06_IfcOpenHouse_coin(self):
        f = FILES[5]
        ifc_import.insert(
            f, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True
        )
        self.failUnless(True, "import failed")

    # def test07_IfcOpenHouse_coin(self):
    #    f = FILES[6]
    #    ifc_import.insert(f, "IfcTest", strategy=0, shapemode=1, switchwb=0, silent=True)
    #    self.failUnless(True, "import failed")


def test():
    "Thius is meant to be used from a terminal, to run the tests without the GUI"

    print("COIN MODE")
    for f in FILES:
        d = FreeCAD.newDocument()
        ifc_import.insert(
            os.path.expanduser("~") + os.sep + f,
            d.Name,
            strategy=0,
            shapemode=1,
            switchwb=0,
            silent=True,
        )
