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

TAB = 2


def get_geometry_tree(element, prefix=""):
    """Returns a list of elements representing an object's representation"""

    result = [prefix + str(element)]
    prefix += TAB * " "
    if getattr(element, "Representation", None):
        reps = element.Representation
        result.append(prefix + str(reps))
        prefix += prefix
        for rep in reps.Representations:
            result.extend(get_geometry_tree(rep, prefix))
    elif getattr(element, "Items", None):
        for it in element.Items:
            result.extend(get_geometry_tree(it, prefix))
    elif element.is_a("IfcPolyline"):
        for p in element.Points:
            result.append(prefix + str(p))
    elif element.is_a("IfcExtrudedAreaSolid"):
        result.append(prefix + str(element.ExtrudedDirection))
        result.extend(get_geometry_tree(element.SweptArea, prefix))
    elif element.is_a("IfcArbitraryClosedProfileDef"):
        result.extend(get_geometry_tree(element.OuterCurve, prefix))
    elif element.is_a("IfcMappedItem"):
        result.extend(get_geometry_tree(element.MappingSource[1], prefix))
    elif element.is_a("IfcBooleanClippingResult"):
        result.extend(get_geometry_tree(element.FirstOperand, prefix))
        result.extend(get_geometry_tree(element.SecondOperand, prefix))
    elif element.is_a("IfcBooleanResult"):
        result.extend(get_geometry_tree(element.FirstOperand, prefix))
        result.extend(get_geometry_tree(element.SecondOperand, prefix))
    elif element.is_a("IfcHalfSpaceSolid"):
        result.extend(get_geometry_tree(element.BaseSurface, prefix))
    return result


def print_geometry_tree(element):
    """Same as get_geometry_tree but printed"""

    for line in get_geometry_tree(element):
        print(line)


def show_geometry_tree(element):
    """Same as get_geometry_tree but in a Qt dialog"""

    import FreeCADGui  # lazy import
    from PySide2 import QtGui, QtWidgets

    path = os.path.dirname(__file__)
    dlg = FreeCADGui.PySideUic.loadUi(os.path.join(path, "ui", "dialogTree.ui"))
    tops = {}
    for line in get_geometry_tree(element):
        psize = (len(line) - len(line.lstrip())) / TAB
        wline = QtWidgets.QTreeWidgetItem([line.lstrip()])
        if not psize:
            dlg.treeWidget.addTopLevelItem(wline)
        else:
            parent = tops[psize - 1]
            parent.addChild(wline)
        tops[psize] = wline
    dlg.treeWidget.expandAll()
    dlg.setWindowTitle(dlg.windowTitle() + " " + element.Name)
    result = dlg.exec_()
