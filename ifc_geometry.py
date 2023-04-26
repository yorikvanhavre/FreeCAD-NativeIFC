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

import FreeCAD

import ifcopenshell
from ifcopenshell.util import unit

import ifc_tools


def add_geom_properties(obj):
    """Adds geometry properties to a FreeCAD object"""

    element = ifc_tools.get_ifc_element(obj)
    if not ifc_tools.has_representation(element):
        return
    ifcfile = ifc_tools.get_ifcfile(obj)
    scaling = ifcopenshell.util.unit.calculate_unit_scale(ifcfile)
    scaling = scaling * 1000  # given scale is for m, we work in mm
    for rep in element.Representation.Representations:
        if rep.RepresentationIdentifier == "Body":
            # Extrusion of a rectangle
            if len(rep.Items) == 1:
                if rep.Items[0].is_a("IfcExtrudedAreaSolid"):
                    ext = rep.Items[0]
                    if "ExtrusionDepth" not in obj.PropertiesList:
                        obj.addProperty(
                            "App::PropertyLength", "ExtrusionDepth", "Geometry"
                        )
                    obj.ExtrusionDepth = ext.Depth * scaling
                    if "ExtrusionDirection" not in obj.PropertiesList:
                        obj.addProperty(
                            "App::PropertyVector", "ExtrusionDirection", "Geometry"
                        )
                    obj.ExtrusionDirection = FreeCAD.Vector(
                        ext.ExtrudedDirection.DirectionRatios
                    )
                    if ext.SweptArea.is_a("IfcRectangleProfileDef"):
                        if "RectangleLength" not in obj.PropertiesList:
                            obj.addProperty(
                                "App::PropertyLength", "RectangleLength", "Geometry"
                            )
                        obj.RectangleLength = ext.SweptArea.XDim * scaling
                        if "RectangleWidth" not in obj.PropertiesList:
                            obj.addProperty(
                                "App::PropertyLength", "RectangleWidth", "Geometry"
                            )
                        obj.RectangleWidth = ext.SweptArea.YDim * scaling

        # below is disabled for now... Don't know if it's useful to expose to the user
        elif False:  # rep.RepresentationIdentifier == "Axis":
            # Wall axis consisting on a single line
            if len(rep.Items) == 1:
                if rep.Items[0].is_a("IfcCompositeCurve"):
                    if len(rep.Items[0].Segments) == 1:
                        if rep.Items[0].Segments[0].is_a("IfcCompositeCurveSegment"):
                            if rep.Items[0].Segments[0].ParentCurve.is_a("IfcPolyline"):
                                pol = rep.Items[0].Segments[0].ParentCurve
                                if len(pol.Points) == 2:
                                    if "AxisStart" not in obj.PropertiesList:
                                        obj.addProperty(
                                            "App::PropertyPosition",
                                            "AxisStart",
                                            "Geometry",
                                        )
                                    obj.AxisStart = FreeCAD.Vector(
                                        pol.Points[0].Coordinates
                                    ).multiply(scaling)
                                    if "AxisEnd" not in obj.PropertiesList:
                                        obj.addProperty(
                                            "App::PropertyPosition",
                                            "AxisEnd",
                                            "Geometry",
                                        )
                                    obj.AxisEnd = FreeCAD.Vector(
                                        pol.Points[1].Coordinates
                                    ).multiply(scaling)


def set_geom_property(obj, prop):
    """Updates the internal IFC file with the given value"""

    element = ifc_tools.get_ifc_element(obj)
    if not ifc_tools.has_representation(element):
        return False
    ifcfile = ifc_tools.get_ifcfile(obj)
    scaling = ifcopenshell.util.unit.calculate_unit_scale(ifcfile)
    scaling = 0.001 / scaling

    print("Debug: Changing prop", obj.Label, ":", prop, "to", getattr(obj, prop))

    if prop == "ExtrusionDepth":
        for rep in element.Representation.Representations:
            if rep.RepresentationIdentifier == "Body":
                if len(rep.Items) == 1:
                    if rep.Items[0].is_a("IfcExtrudedAreaSolid"):
                        elem = rep.Items[0]
                        depth = getattr(obj, prop).Value * scaling
                        ifcopenshell.api.run(
                            "attribute.edit_attributes",
                            ifcfile,
                            product=elem,
                            attributes={"Depth": depth},
                        )
                        return True

    elif prop == "ExtrusionDirection":
        for rep in element.Representation.Representations:
            if rep.RepresentationIdentifier == "Body":
                if len(rep.Items) == 1:
                    if rep.Items[0].is_a("IfcExtrudedAreaSolid"):
                        elem = rep.Items[0].ExtrudedDirection
                        direction = tuple(getattr(obj, prop))
                        ifcopenshell.api.run(
                            "attribute.edit_attributes",
                            ifcfile,
                            product=elem,
                            attributes={"DirectionRatios": direction},
                        )
                        return True

    elif prop == "RectangleLength":
        for rep in element.Representation.Representations:
            if rep.RepresentationIdentifier == "Body":
                if len(rep.Items) == 1:
                    if rep.Items[0].is_a("IfcExtrudedAreaSolid"):
                        elem = rep.Items[0].SweptArea
                        if elem.is_a("IfcRectangleProfileDef"):
                            value = getattr(obj, prop).Value * scaling
                            ifcopenshell.api.run(
                                "attribute.edit_attributes",
                                ifcfile,
                                product=elem,
                                attributes={"XDim": value},
                            )
                            return True

    elif prop == "RectangleWidth":
        for rep in element.Representation.Representations:
            if rep.RepresentationIdentifier == "Body":
                if len(rep.Items) == 1:
                    if rep.Items[0].is_a("IfcExtrudedAreaSolid"):
                        elem = rep.Items[0].SweptArea
                        if elem.is_a("IfcRectangleProfileDef"):
                            value = getattr(obj, prop).Value * scaling
                            ifcopenshell.api.run(
                                "attribute.edit_attributes",
                                ifcfile,
                                product=elem,
                                attributes={"YDim": value},
                            )
                            return True

    return False
