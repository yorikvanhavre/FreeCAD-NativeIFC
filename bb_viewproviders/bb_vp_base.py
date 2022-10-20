#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2022 Yorik van Havre <yorik@uncreated.net>              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

class bb_vp_base:
    
    """Base class for all blenderbim view providers"""
    
    def __init__(self, vobj):
        vobj.Proxy = self
    
    def attach(self, vobj):
        self.Object = vobj.Object
   
    def getDisplayModes(self,obj):
        return []

    def getDefaultDisplayMode(self):
        return "FlatLines"

    def setDisplayMode(self,mode):
        return mode

    def onChanged(self, vp, prop):
        return

    def updateData(self, fp, prop):
        return

    def __getstate__(self):
        return None

    def __setstate__(self,state):
        return None
    
    def claimChildren(self):
        children = []
        relprops = ["Item","ForLayerSet"] # properties that actually store parents
        for prop in self.Object.PropertiesList:
            if prop.startswith("Relating") or (prop in relprops):
                continue
            else:
                value = getattr(self.Object, prop)
                if hasattr(value, "ViewObject"):
                    children.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if hasattr(item, "ViewObject"):
                            children.append(item)
        for parent in self.Object.InList:
            for prop in parent.PropertiesList:
                if prop.startswith("Relating") or (prop in relprops):
                    value = getattr(parent, prop)
                    if value == self.Object:
                        children.append(parent)
        return children
