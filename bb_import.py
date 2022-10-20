# ***************************************************************************
# *   Copyright (c) 2022 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import os
import multiprocessing
import time

import FreeCAD
import ifcopenshell
from ifcopenshell import geom
from bb_viewproviders import bb_vp_document
import Part

SCALE = 1000.0 # IfcOpenShell works in meters, FreeCAD works in mm


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
    create_document(filename, document)
    document.recompute()
    endtime = "%02d:%02d" % (divmod(round(time.time() - stime, 1), 60))
    fsize = round(os.path.getsize(filename)/1048576, 2)
    print ("Imported", fsize, "Mb in", endtime)


def create_document(filename, document):

    """Creates a FreeCAD IFC document object"""

    obj = document.addObject("Part::FeaturePython","IfcDocument")
    obj.addProperty("App::PropertyString","FilePath","Base","The path to the linked IFC file")
    obj.FilePath = filename
    f = ifcopenshell.open(filename)
    p = f.by_type("IfcProject")[0]
    add_properties(p, obj)
    if FreeCAD.GuiUp:
        bb_vp_document.bb_vp_document(obj.ViewObject)
    geoms = ifcopenshell.util.element.get_decomposition(p)
    obj.Shape = get_shape(geoms, f)



def create_object(ifcentity, document):

    """Creates a FreeCAD object from an IFC entity"""

    obj = document.addObject("App::FeaturePython","IfcObject")
    add_properties(ifcentity, obj)


def add_properties(ifcentity, obj):

    """Adds the properties of the given IFC object to a FreeCAD object"""

    if getattr(ifcentity, "Name", None):
        obj.Label = ifcentity.Name
    else:
        obj.Label = ifcentity.is_a()
    for attr, value in ifcentity.get_info().items():
        if attr == "id":
            attr = "StepId"
        elif attr == "type":
            attr = "Type"
        elif attr == "Name":
            continue
        if attr not in obj.PropertiesList:
            if isinstance(value, int):
                obj.addProperty("App::PropertyInteger", attr, "IFC")
                setattr(obj, attr, value)
            elif isinstance(value, float):
                obj.addProperty("App::PropertyFloat", attr, "IFC")
                setattr(obj, attr, value)
            elif isinstance(value, ifcopenshell.entity_instance):
                #value = create_object(value)
                obj.addProperty("App::PropertyLink", attr, "IFC")
                #setattr(obj, attr, value)
            elif isinstance(value, (list, tuple)) and value:
                if isinstance(value[0], ifcopenshell.entity_instance):
                    nvalue = []
                    #for elt in value:
                    #    nvalue.append(create_object(elt))
                    obj.addProperty("App::PropertyLinkList", attr, "IFC")
                    #setattr(obj, attr, nvalue)
            else:
                obj.addProperty("App::PropertyString", attr, "IFC")
                if value is not None:
                    setattr(obj, attr, str(value))


def get_shape(geoms, ifcfile):

    """Returns a Part shape from a list of IFC entities"""

    settings = ifcopenshell.geom.settings()
    settings.set(settings.DISABLE_TRIANGULATION, True)
    settings.set(settings.USE_BREP_DATA,True)
    settings.set(settings.SEW_SHELLS,True)
    shapes = []
    cores = multiprocessing.cpu_count()
    geoms = [g for g in geoms if (not g.is_a("IfcFurnishingElement") and not g.is_a("IfcSpace"))]
    iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=geoms)
    iterator.initialize()
    while True:
        item = iterator.get()
        if item:
            brep = item.geometry.brep_data
            shape = Part.Shape()
            shape.importBrepFromString(brep, False)
            mat = get_matrix(item.transformation.matrix.data)
            shape.scale(SCALE)
            shape.transformShape(mat)
            shapes.append(shape)
        if not iterator.next():
            break
    return Part.makeCompound(shapes)


def get_matrix(ios_matrix):

    """Converts an IfcOpenShell matrix tuple into a FreeCAD matrix"""

    # https://github.com/IfcOpenShell/IfcOpenShell/issues/1440
    # https://pythoncvc.net/?cat=203
    m_l = list()
    for i in range(3):
        line = list(ios_matrix[i::3])
        line[-1] *= SCALE
        m_l.extend(line)
    return FreeCAD.Matrix(*m_l)
