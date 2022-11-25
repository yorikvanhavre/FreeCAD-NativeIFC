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


def insert(filename, docname):

    """Inserts an IFC document in a FreeCAD document"""

    stime = time.time()
    document = FreeCAD.getDocument(docname)
    ifc_tools.create_document(filename, document)
    document.recompute()
    endtime = "%02d:%02d" % (divmod(round(time.time() - stime, 1), 60))
    fsize = round(os.path.getsize(filename)/1048576, 2)
    print ("Imported", fsize, "Mb in", endtime)
    if FreeCAD.GuiUp:
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/Start")
        p = p.GetString("AutoloadModule","")
        if p:
            import FreeCADGui
            FreeCADGui.activateWorkbench("BIMWorkbench")

