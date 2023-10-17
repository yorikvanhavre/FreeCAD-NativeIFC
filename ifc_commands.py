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

"""This module contains IFC-related FreeCAD commands"""


import os
import FreeCAD
import FreeCADGui


def QT_TRANSLATE_NOOP(scope, text):
    return text

def get_project():
    """Gets the current project"""

    import ifc_tools

    if FreeCADGui.Selection.getSelection():
        return ifc_tools.get_project(FreeCADGui.Selection.getSelection()[0])
    else:
        return ifc_tools.get_project(FreeCAD.ActiveDocument)


class IFC_Diff:
    """Shows a diff of the changes in the current IFC document"""

    def GetResources(self):
        tt = QT_TRANSLATE_NOOP("IFC_Diff", "Shows the current unsaved changes in the IFC file")
        return {
            "Pixmap": os.path.join(os.path.dirname(__file__), "icons", "IFC.svg"),
            "MenuText": QT_TRANSLATE_NOOP("IFC_Diff", "IFC Diff..."),
            "ToolTip": tt,
            "Accel": "I, D",
        }

    def Activated(self):
        import ifc_diff

        proj = get_project()
        if proj:
            diff = ifc_diff.get_diff(proj)
            ifc_diff.show_diff(diff)


class IFC_Expand:
    """Expands the children of the selected objects or document"""

    def GetResources(self):
        tt = QT_TRANSLATE_NOOP("IFC_Expand", "Expands the children of the selected objects or document")
        return {
            "Pixmap": os.path.join(os.path.dirname(__file__), "icons", "IFC.svg"),
            "MenuText": QT_TRANSLATE_NOOP("IFC_Expand", "IFC Expand"),
            "ToolTip": tt,
            "Accel": "I, E",
        }

    def Activated(self):
        ns = []
        for obj in FreeCADGui.Selection.getSelection():
            if hasattr(obj.ViewObject, "Proxy"):
                if hasattr(obj.ViewObject.Proxy, "hasChildren"):
                    if obj.ViewObject.Proxy.hasChildren(obj):
                        no = obj.ViewObject.Proxy.expandChildren(obj)
                        ns.extend(no)
        else:
            import ifc_generator
            import ifc_tools

            document = FreeCAD.ActiveDocument
            ifc_generator.delete_ghost(document)
            ifcfile = ifc_tools.get_ifcfile(document)
            if ifcfile:
                ns = ifc_tools.create_children(document, ifcfile, recursive=True, only_structure=True)
        if ns:
            document.recompute()
            FreeCADGui.Selection.clearSelection()
            for o in ns:
                FreeCADGui.Selection.addSelection(o)
