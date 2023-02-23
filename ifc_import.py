#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2022 Yorik van Havre <yorik@uncreated.net>              *
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
import FreeCAD
import ifc_tools



def open(filename):

    """Opens an IFC file"""

    name = os.path.splitext(os.path.basename(filename))[0]
    doc = FreeCAD.newDocument()
    doc.Label = name
    FreeCAD.setActiveDocument(doc.Name)
    insert(filename,doc.Name)
    return doc


def insert(filename, docname, strategy=None, shapemode=None, switchwb=None, silent=False):

    """Inserts an IFC document in a FreeCAD document"""

    strategy, shapemode, switchwb = get_options(strategy, shapemode, switchwb, silent)
    if strategy is None:
        print("Aborted.")
        return
    stime = time.time()
    document = FreeCAD.getDocument(docname)
    ifc_tools.create_document(filename, document, shapemode, strategy)
    document.recompute()
    endtime = "%02d:%02d" % (divmod(round(time.time() - stime, 1), 60))
    fsize = round(os.path.getsize(filename)/1048576, 2)
    print ("Imported", os.path.basename(filename), "(", fsize, "Mb ) in", endtime)
    if FreeCAD.GuiUp and switchwb:
        from StartPage import StartPage
        StartPage.postStart()
    return document


def get_options(strategy=None, shapemode=None, switchwb=None, silent=False):

    """Shows a dialog to get import options

    shapemode: 0 = full shape
               1 = coin only
    strategy:  0 = only root object
               1 = only bbuilding structure,
               2 = all children
    """

    params = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/NativeIFC")
    if strategy is None:
        strategy = params.GetInt("ImportStrategy",0)
    if shapemode is None:
        shapemode = params.GetInt("ShapeMode",0)
    if switchwb is None:
        switchwb = params.GetBool("SwitchWB",True)
    if silent:
        return strategy, shapemode, switchwb
    ask = params.GetBool("AskAgain",True)
    if ask and FreeCAD.GuiUp:
        import FreeCADGui
        from PySide import QtGui
        dlg = FreeCADGui.PySideUic.loadUi(os.path.join(os.path.dirname(__file__),"ui","dialogImport.ui"))
        dlg.comboStrategy.setCurrentIndex(strategy)
        dlg.comboShapeMode.setCurrentIndex(shapemode)
        dlg.checkSwitchWB.setChecked(switchwb)
        dlg.checkAskAgain.setChecked(ask)
        result = dlg.exec_()
        if not result:
            return None, None, None
        strategy = dlg.comboStrategy.currentIndex()
        shapemode = dlg.comboShapeMode.currentIndex()
        switchwb = dlg.checkSwitchWB.isChecked()
        ask = dlg.checkAskAgain.isChecked()
        params.SetInt("ImportStrategy",strategy)
        params.SetInt("ShapeMode",shapemode)
        params.SetBool("SwitchWB",switchwb)
        params.SetBool("AskAgain",ask)
    return strategy, shapemode, switchwb
