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

class ifc_object:
    
    """Base class for all blenderbim objects"""
    
    def onChanged(self, obj, prop):
        return

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None
    
    def execute (self, obj):
        
        import Part # lazy import

        shapes = [child.Shape for child in obj.Group if hasattr(child,"Shape")]
        if shapes:
            siteshape = getattr(obj,"SiteShape",None)
            if siteshape:
                obj.Shape = siteshape
            else:
                obj.Shape = Part.makeCompound(shapes)

    def get_ifc_element(self, obj):

        import ifc_tools # lazy import

        ifc_file = ifc_tools.get_ifcfile(obj)
        if ifc_file and hasattr(obj, "StepId"):
            return ifc_file.by_id(obj.StepId)
        return None
