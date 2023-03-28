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
import multiprocessing

import FreeCAD
from FreeCAD import Base
import Part
import Mesh
from pivy import coin

import ifcopenshell
from ifcopenshell import geom
from ifcopenshell import api
from ifcopenshell import template
from ifcopenshell.util import attribute
from ifcopenshell.util import schema

import ifc_objects
import ifc_viewproviders

SCALE = 1000.0 # IfcOpenShell works in meters, FreeCAD works in mm


def create_document(document, filename=None, shapemode=0, strategy=0):

    """Creates a IFC document object in the given FreeCAD document.

    filename:  If not given, a blank IFC document is created
    shapemode: 0 = full shape
               1 = coin only
               2 = no representation
    strategy:  0 = only root object
               1 = only bbuilding structure,
               2 = all children
    """

    obj = add_object(document, project=True)
    d = "The path to the linked IFC file"
    obj.addProperty("App::PropertyFile","FilePath","Base",d)
    obj.addProperty("App::PropertyBool","Modified","Base")
    obj.setPropertyStatus("Modified","Hidden")
    if filename:
        obj.FilePath = filename
        ifcfile = ifcopenshell.open(filename)
    else:
        ifcfile = create_ifcfile()
    project = ifcfile.by_type("IfcProject")[0]
    obj.Proxy.ifcfile = ifcfile
    add_properties(obj, ifcfile, project, shapemode=shapemode)
    # populate according to strategy
    if strategy == 0:
        pass
    elif strategy == 1:
        create_children(obj, ifcfile, recursive=True, only_structure=True)
    elif strategy == 2:
        create_children(obj, ifcfile, recursive=True, assemblies=False)
    return obj


def create_ifcfile():

    """Creates a new, empty IFC document"""

    ifcfile = ifcopenshell.template.create()
    param = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document")
    user = param.GetString("prefAuthor","")
    user = user.split("<")[0].strip()
    if user:
        person = ifcfile.by_type("IfcPerson")[0]
        set_attribute(ifcfile, person, "FamilyName", user)
    org = param.GetString("prefCompany","")
    if org:
        comp = ifcfile.by_type("IfcOrganization")[0]
        set_attribute(ifcfile, comp, "Name", user)
    application = "FreeCAD"
    version = FreeCAD.Version()
    version = ".".join([str(v) for v in version[0:3]])
    app = ifcfile.by_type("IfcApplication")[0]
    set_attribute(ifcfile, app, "ApplicationFullName", application)
    set_attribute(ifcfile, app, "Version", version)
    return ifcfile


def create_object(ifcentity, document, ifcfile, shapemode=0):

    """Creates a FreeCAD object from an IFC entity"""

    s = "Created #{}: {}, '{}'\n".format(ifcentity.id(), ifcentity.is_a(), ifcentity.Name)
    FreeCAD.Console.PrintLog(s)
    obj = add_object(document)
    add_properties(obj, ifcfile, ifcentity, shapemode=shapemode)
    elements = [ifcentity]
    return obj


def create_children(obj, ifcfile=None, recursive=False, only_structure=False, assemblies=True):

    """Creates a hierarchy of objects under an object"""

    def create_child(parent, element):
        subresult = []
        # do not create if a child with same stepid already exists
        if not element.id() in [getattr(c,"StepId",0) for c in getattr(parent,"Group",[])]:
            child = create_object(element, parent.Document, ifcfile, parent.ShapeMode)
            subresult.append(child)
            parent.addObject(child)
            if element.is_a("IfcSite"):
                # force-create contained buildings too if we just created a site
                buildings = [o for o in get_children(child, ifcfile) if o.is_a("IfcBuilding")]
                for building in buildings:
                    subresult.extend(create_child(child, building))
            if recursive:
                subresult.extend(create_children(child, ifcfile, recursive, only_structure, assemblies))
        return subresult

    if not ifcfile:
        ifcfile = get_ifcfile(obj)
    result = []
    for child in get_children(obj, ifcfile, only_structure, assemblies):
        result.extend(create_child(obj, child))
    return result


def get_children(obj, ifcfile, only_structure=False, assemblies=True):

    """Returns the direct descendants of an object"""

    ifcentity = ifcfile[obj.StepId]
    children = []
    if assemblies or not ifcentity.is_a("IfcElement"):
        for rel in getattr(ifcentity, "IsDecomposedBy", []):
            children.extend(rel.RelatedObjects)
    if not only_structure:
        for rel in getattr(ifcentity, "ContainsElements", []):
            children.extend(rel.RelatedElements)
        for rel in getattr(ifcentity, "HasOpenings", []):
            children.extend([rel.RelatedOpeningElement])
        for rel in getattr(ifcentity, "HasFillings", []):
            children.extend([rel.RelatedBuildingElement])
    return filter_elements(children, ifcfile, expand=False)


def get_ifcfile(obj):

    """Returns the ifcfile that handles this object"""

    project = get_project(obj)
    if project:
        if hasattr(project,"Proxy"):
            if hasattr(project.Proxy,"ifcfile"):
                return project.Proxy.ifcfile
        if project.FilePath:
            ifcfile = ifcopenshell.open(project.FilePath)
            if hasattr(project,"Proxy"):
                project.Proxy.ifcfile = ifcfile
            return ifcfile
    return None


def get_project(obj):

    """Returns the ifcdocument this object belongs to"""

    proj_types = ("IfcProject","IfcProjectLibrary")
    if getattr(obj, "Type", None) in proj_types:
        return obj
    if hasattr(obj,"InListRecursive"):
        for parent in obj.InListRecursive:
            if getattr(parent, "Type", None) in proj_types:
                return parent
    return None


def can_expand(obj, ifcfile):

    """Returns True if this object can have any more child extracted"""

    children = get_children(obj, ifcfile)
    group = [o.StepId for o in obj.Group]
    for child in children:
        if child.id() not in group:
            return True
    return False


def add_object(document, project=False):

    """adds a new object to a FreeCAD document"""

    proxy = ifc_objects.ifc_object()
    if project:
        vp = ifc_viewproviders.ifc_vp_document()
    else:
        vp = ifc_viewproviders.ifc_vp_object()
    obj = document.addObject('Part::FeaturePython', 'IfcObject', proxy, vp, False)
    return obj


def add_properties(obj, ifcfile=None ,ifcentity=None, links=False, shapemode=0, short=True):

    """Adds the properties of the given IFC object to a FreeCAD object"""

    if not ifcfile:
        ifcfile = get_ifcfile(obj)
    if not ifcentity:
        ifcentity = get_ifc_element(obj)
    if getattr(ifcentity, "Name", None):
        obj.Label = ifcentity.Name
    else:
        obj.Label = ifcentity.is_a()
    if not obj.hasExtension("App::GroupExtensionPython"):
        obj.addExtension('App::GroupExtensionPython')
    if FreeCAD.GuiUp:
        obj.ViewObject.addExtension("Gui::ViewProviderGroupExtensionPython")
    if "ShapeMode" not in obj.PropertiesList:
        obj.addProperty("App::PropertyEnumeration", "ShapeMode", "Base")
        shapemodes = ["Shape","Coin","None"] # possible shape modes for all IFC objects
        if isinstance(shapemode,int):
            shapemode = shapemodes[shapemode]
        obj.ShapeMode = shapemodes
        obj.ShapeMode = shapemode
    attr_defs = ifcentity.wrapped_data.declaration().as_entity().all_attributes()
    try:
        info_ifcentity = ifcentity.get_info()
    except:
        # slower but no errors
        info_ifcentity = get_elem_attribs(ifcentity)
    for attr, value in info_ifcentity.items():
        if attr == "type":
            attr = "Type"
        elif attr == "id":
            attr = "StepId"
        elif attr == "Name":
            continue
        if short and attr not in ("Type","StepId"):
            continue
        attr_def = next((a for a in attr_defs if a.name() == attr), None)
        data_type = ifcopenshell.util.attribute.get_primitive_type(attr_def) if attr_def else None
        if attr == "Type":
            # main enum property, not saved to file
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", attr, "IFC")
                obj.setPropertyStatus(attr,"Transient")
            setattr(obj, attr, get_ifc_classes(obj, value))
            setattr(obj, attr, value)
            # companion hidden propertym that gets saved to file
            obj.addProperty("App::PropertyString", "IfcType", "IFC")
            obj.setPropertyStatus("IfcType","Hidden")
            setattr(obj, "IfcType", value)
        elif isinstance(value, int):
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyInteger", attr, "IFC")
                if attr == "StepId":
                    obj.setPropertyStatus(attr,"ReadOnly")
            setattr(obj, attr, value)
        elif isinstance(value, float):
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyFloat", attr, "IFC")
            setattr(obj, attr, value)
        elif data_type == "boolean":
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyBool", attr, "IFC")
            setattr(obj, attr, value) #will trigger error. TODO: Fix this
        elif isinstance(value, ifcopenshell.entity_instance):
            if links:
                if attr not in obj.PropertiesList:
                    #value = create_object(value, obj.Document)
                    obj.addProperty("App::PropertyLink", attr, "IFC")
                #setattr(obj, attr, value)
        elif isinstance(value, (list, tuple)) and value:
            if isinstance(value[0], ifcopenshell.entity_instance):
                if links:
                    if attr not in obj.PropertiesList:
                        #nvalue = []
                        #for elt in value:
                        #    nvalue.append(create_object(elt, obj.Document))
                        obj.addProperty("App::PropertyLinkList", attr, "IFC")
                    #setattr(obj, attr, nvalue)
        elif data_type == "enum":
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyEnumeration", attr, "IFC")
            items = ifcopenshell.util.attribute.get_enum_items(attr_def)
            setattr(obj, attr, items)
            if not value in items:
                for v in ("UNDEFINED","NOTDEFINED","USERDEFINED"):
                    if v in items:
                        value = v
                        break
            if value in items:
                setattr(obj, attr, value)
        else:
            if attr not in obj.PropertiesList:
                obj.addProperty("App::PropertyString", attr, "IFC")
            if value is not None:
                setattr(obj, attr, str(value))


def remove_unused_properties(obj):

    """Remove IFC properties if they are not part of the current IFC class"""

    elt = get_ifc_element(obj)
    props = list(elt.get_info().keys())
    props[props.index("id")] = "StepId"
    props[props.index("type")] = "Type"
    for prop in obj.PropertiesList:
        if obj.getGroupOfProperty(prop) == "IFC":
            if prop not in props:
                obj.removeProperty(prop)


def get_ifc_classes(obj, baseclass):

    """Returns a list of sibling classes from a given FreeCAD object"""

    if baseclass in ("IfcProject","IfcProjectLibrary"):
        return ("IfcProject","IfcProjectLibrary")
    ifcfile = get_ifcfile(obj)
    if not ifcfile:
        return [baseclass]
    schema = ifcfile.wrapped_data.schema_name()
    schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(schema)
    declaration = schema.declaration_by_name(baseclass)
    if "StandardCase" in baseclass:
        declaration = declaration.supertype()
    classes = [sub.name() for sub in declaration.supertype().subtypes()]
    # also include subtypes of the current class (ex, StandardCases)
    classes.extend([sub.name() for sub in declaration.subtypes()])
    if not baseclass in classes:
        classes.append(baseclass)
    return classes


def get_ifc_element(obj):

    """Returns the corresponding IFC element of an object"""

    ifc_file = get_ifcfile(obj)
    if ifc_file and hasattr(obj, "StepId"):
        return ifc_file.by_id(obj.StepId)
    return None


def has_representation(element):

    """Tells if an elements has an own representation"""

    if hasattr(element,"Representation") and element.Representation:
        return True
    return False


def filter_elements(elements, ifcfile, expand=True):

    """Filter elements list of unwanted types"""

    # gather decomposition if needed
    if expand and (len(elements) == 1):
        elem = elements[0]
        if not has_representation(elem):
            if elem.is_a("IfcProject"):
                elements = ifcfile.by_type("IfcElement")
                elements.extend(ifcfile.by_type("IfcSite"))
            else:
                elements = ifcopenshell.util.element.get_decomposition(elem)
        else:
            if elem.Representation.Representations:
                rep = elem.Representation.Representations[0]
                if (
                    rep.Items and rep.Items[0].is_a() == "IfcPolyline"
                    and elem.IsDecomposedBy
                ):
                    # only use the decomposition and not the polyline
                    # happens for multilayered walls exported by VectorWorks
                    # the Polyline is the wall axis
                    # see https://github.com/yorikvanhavre/FreeCAD-NativeIFC/issues/28
                    elements = ifcopenshell.util.element.get_decomposition(elem)
    # Never load feature elements, they can be lazy loaded
    elements = [e for e in elements if not e.is_a("IfcFeatureElement")]
    # do not load spaces for now (TODO handle them correctly)
    elements = [e for e in elements if not e.is_a("IfcSpace")]
    # skip projects
    elements = [e for e in elements if not e.is_a("IfcProject")]
    # skip furniture for now, they can be lazy loaded probably
    elements = [e for e in elements if not e.is_a("IfcFurnishingElement")]
    # skip annotations for now
    elements = [e for e in elements if not e.is_a("IfcAnnotation")]
    return elements


def get_cache(ifcfile):

    """Returns the shape cache dictionary associated with this ifc file"""

    for d in FreeCAD.listDocuments().values():
        for o in d.Objects:
            if hasattr(o,"Proxy") and hasattr(o.Proxy,"ifcfile"):
                if o.Proxy.ifcfile == ifcfile:
                    if hasattr(o.Proxy,"ifccache") and o.Proxy.ifccache:
                        return o.Proxy.ifccache
    return {"Shape":{},"Color":{},"Coin":{}}


def set_cache(ifcfile, cache):

    """Sets the given dictionary as shape cache for the given ifc file"""

    for d in FreeCAD.listDocuments().values():
        for o in d.Objects:
            if hasattr(o,"Proxy") and hasattr(o.Proxy,"ifcfile"):
                if o.Proxy.ifcfile == ifcfile:
                    o.Proxy.ifccache = cache
                    return


def get_shape(elements, ifcfile, cached=False):

    """Returns a Part shape from a list of IFC entities"""

    elements = filter_elements(elements, ifcfile)
    if len(elements) == 0:
        return None, None  # happens on empty storeys
    shapes = []
    colors = []
    # process cached elements
    cache = get_cache(ifcfile)
    if cached:
        rest = []
        for e in elements:
            if e.id in cache["Shape"]:
                s = cache["Shape"][e.id]
                shapes.append(s.copy())
                if e.id in cache["Color"]:
                    c = cache["Color"][e.id]
                else:
                    c = (0.8,0.8,0.8)
                for f in s.Faces:
                    colors.append(c)
            else:
                rest.append(e)
        elements = rest
    if not elements:
        return shapes, colors
    progressbar = Base.ProgressIndicator()
    total = len(elements)
    progressbar.start("Generating "+str(total)+" shapes...",total)
    iterator = get_geom_iterator(ifcfile, elements, brep=True)
    if iterator is None:
        return None, None
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
            color = item.geometry.surface_styles
            #color = (color[0], color[1], color[2], 1.0 - color[3])
            # TODO temp workaround for tranparency bug
            color = (color[0], color[1], color[2], 0.0)
            for f in shape.Faces:
                colors.append(color)
            cache["Shape"][item.id]=shape
            cache["Color"][item.id]=color
            progressbar.next(True)
        if not iterator.next():
            break
    set_cache(ifcfile, cache)
    if len(shapes) == 1:
        shape = shapes[0]
    else:
        shape = Part.makeCompound(shapes)
    progressbar.stop()
    return shape, colors


def get_coin(elements, ifcfile, cached=False):

    """Returns a Coin node from a list of IFC entities"""

    elements = filter_elements(elements, ifcfile)
    nodes = coin.SoSeparator()
    # process cached elements
    cache = get_cache(ifcfile)
    if cached:
        rest = []
        for e in elements:
            if e.id() in cache["Coin"]:
                nodes.addChild(cache["Coin"][e.id()].copy())
            else:
                rest.append(e)
        elements = rest
    elements = [e for e in elements if has_representation(e)]
    if not elements:
        return nodes, None
    if nodes.getNumChildren():
        print("DEBUG: The following elements are excluded because they make coin crash (need to investigate):")
        print("DEBUG: If you wish to test, comment out line 488 (return nodes, None) in ifc_tools.py")
        [print("   ", e) for e in elements]
        return nodes, None
    progressbar = Base.ProgressIndicator()
    total = len(elements)
    progressbar.start("Generating "+str(total)+" shapes...",total)
    iterator = get_geom_iterator(ifcfile, elements, brep=False)
    if iterator is None:
        return None, None
    while True:
        item = iterator.get()
        if item:
            node = coin.SoSeparator()
            # colors
            if item.geometry.materials:
                color = item.geometry.materials[0].diffuse
                color = (color[0], color[1], color[2], 0.0)
                mat = coin.SoMaterial()
                mat.diffuseColor.setValue(color[:3])
                # TODO treat transparency
                #mat.transparency.setValue(0.8)
                node.addChild(mat)
            # verts
            matrix = get_matrix(item.transformation.matrix.data)
            verts = item.geometry.verts
            verts = [FreeCAD.Vector(verts[i:i+3]) for i in range(0,len(verts),3)]
            verts = [tuple(matrix.multVec(v.multiply(SCALE))) for v  in verts]
            coords = coin.SoCoordinate3()
            coords.point.setValues(verts)
            node.addChild(coords)
            # faces
            faces = list(item.geometry.faces)
            faces = [f for i in range(0,len(faces),3) for f in faces[i:i+3]+[-1]]
            faceset = coin.SoIndexedFaceSet()
            faceset.coordIndex.setValues(faces)
            node.addChild(faceset)
            nodes.addChild(node)
            cache["Coin"][item.id] = node
            progressbar.next(True)
        if not iterator.next():
            break
    set_cache(ifcfile, cache)
    progressbar.stop()
    return nodes, None


def get_settings(ifcfile, brep=True):

    """Returns ifcopenshell settings"""

    settings = ifcopenshell.geom.settings()
    if brep:
        settings.set(settings.DISABLE_TRIANGULATION, True)
        settings.set(settings.USE_BREP_DATA,True)
        settings.set(settings.SEW_SHELLS,True)
    body_contexts = get_body_context_ids(ifcfile)
    if body_contexts:
        settings.set_context_ids(body_contexts)
    return settings


def get_geom_iterator(ifcfile, elements, brep):

    settings = get_settings(ifcfile, brep)
    cores = multiprocessing.cpu_count()
    iterator = ifcopenshell.geom.iterator(settings, ifcfile, cores, include=elements)
    if not iterator.initialize():
        print("  DEBUG: ifc_tools.get_geom_iterator: Invalid iterator")
        return None

    return iterator


def set_geometry(obj, elem, ifcfile, cached=False):

    """Sets the geometry of the given object
    obj: FreeCAD document object
    elem: IfcOpenShell ifc entity instance
    ifcfile: IfcOpenShell ifc file instance
    """

    if not obj or not elem or not ifcfile:
        return
    basenode = None
    colors = None
    if obj.ViewObject:
        # getChild(2) is master on/off switch,
        # getChild(0) is flatlines display mode (1 = shaded, 2 = wireframe, 3 = points)
        basenode = obj.ViewObject.RootNode.getChild(2).getChild(0)
        if basenode.getNumChildren() == 5:
            # Part VP has 4 nodes, we have added 1 more
            basenode.removeChild(4)
    if obj.Group and not(has_representation(get_ifc_element(obj))):
        # workaround for group extension bug: add a dummy placeholder shape)
        # otherwise a shape is force-created from the child shapes
        # and we don't want that otherwise we can't select children
        obj.Shape = Part.makeBox(1,1,1)
        colors = None
    elif obj.ShapeMode == "Shape":
        # set object shape
        shape, colors = get_shape([elem], ifcfile, cached)
        if shape is None:
            if not elem.is_a("IfcContext") and not elem.is_a("IfcSpatialStructureElement"):
                print(
                    "Debug: No Shape returned for object {}, {}, {}"
                    .format(obj.StepId, obj.IfcType, obj.Label)
                )
        else:
            placement = shape.Placement
            obj.Shape = shape
            obj.Placement = placement
    elif basenode and obj.ShapeMode == "Coin":
        if obj.Group:
            # this is for objects that have own coin representation,
            # but shapes among their children and not taken by first if
            # case above. TODO do this more elegantly
            obj.Shape = Part.makeBox(1,1,1)
        # set coin representation
        node, colors = get_coin([elem], ifcfile, cached)
        basenode.addChild(node)
    set_colors(obj, colors)


def set_attribute(ifcfile, element, attribute, value):

    """Sets the value of an attribute of an IFC element"""

    if attribute == "Type":
        if value != element.is_a():
            if value and value.startswith("Ifc"):
                cmd = 'root.reassign_class'
                FreeCAD.Console.PrintLog("Changing IFC class value: "+element.is_a()+" to "+str(value)+"\n")
                product = ifcopenshell.api.run(cmd, ifcfile, product=element, ifc_class=value)
                # TODO fix attributes
                return product
    cmd = 'attribute.edit_attributes'
    attribs = {attribute: value}
    if hasattr(element, attribute):
        if getattr(element, attribute) != value:
            FreeCAD.Console.PrintLog("Changing IFC attribute value of "+str(attribute)+": "+str(value)+"\n")
            ifcopenshell.api.run(cmd, ifcfile, product=element, attributes=attribs)
            return True
    return False


def set_colors(obj, colors):

    """Sets the given colors to an object"""

    if FreeCAD.GuiUp and colors:
        if hasattr(obj.ViewObject,"ShapeColor"):
            obj.ViewObject.ShapeColor = colors[0][:3]
        if hasattr(obj.ViewObject,"DiffuseColor"):
            obj.ViewObject.DiffuseColor = colors


def get_body_context_ids(ifcfile):

    # Facetation is to accommodate broken Revit files
    # See https://forums.buildingsmart.org/t/suggestions-on-how-to-improve-clarity-of-representation-context-usage-in-documentation/3663/6?u=moult
    body_contexts = [
        c.id()
        for c in ifcfile.by_type("IfcGeometricRepresentationSubContext")
        if c.ContextIdentifier in ["Body", "Facetation"]
    ]
    # Ideally, all representations should be in a subcontext, but some BIM programs don't do this correctly
    body_contexts.extend(
        [
            c.id()
            for c in ifcfile.by_type("IfcGeometricRepresentationContext", include_subtypes=False)
            if c.ContextType == "Model"
        ]
    )
    return body_contexts


def get_plan_contexts_ids(ifcfile):

    # Annotation is to accommodate broken Revit files
    # See https://github.com/Autodesk/revit-ifc/issues/187
    return [
        c.id()
        for c in ifcfile.by_type("IfcGeometricRepresentationContext")
        if c.ContextType in ["Plan", "Annotation"]
    ]


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


def save_ifc(obj, filepath=None):

    """Saves the linked IFC file of a project, but does not mark it as saved"""

    if not filepath:
        if hasattr(obj,"FilePath") and obj.FilePath:
            filepath = obj.FilePath
    if filepath:
        ifcfile = get_ifcfile(obj)
        if not ifcfile:
            ifcfile = create_ifcfile()
        ifcfile.write(filepath)
        FreeCAD.Console.PrintMessage("Saved " + filepath + "\n")


def save(obj, filepath=None):

    """Saves the linked IFC file of a project and set its saved status"""

    save_ifc(obj, filepath)
    obj.Modified = False


def ifcize(obj, parent):

    """Takes any FreeCAD object and aggregates it to an existing IFC object"""

    if get_project(obj):
        FreeCAD.Console.PrintError("This object is already part of an IFC project\n")
        return
    proj = get_project(parent)
    if not proj:
        FreeCAD.Console.PrintError("The parent object is not part of an IFC project\n")
        return
    ifcfile = get_ifcfile(proj)
    product = create_product(obj, parent, ifcfile)
    print("created",product)
    newobj = create_object(product, obj.Document, ifcfile)
    print("created obj",newobj)
    rel = create_relationship(newobj, parent, product, ifcfile)
    print("create rel",rel)
    base = getattr(obj,"Base",None)
    if base:
        # make sure the base is used only by this object before deleting
        if base.OutList != [obj]:
            base = None
    obj.Document.removeObject(obj.Name)
    if base:
        obj.Document.removeObject(base.Name)
    return newobj


def create_product(obj, parent, ifcfile):

    """Creates an IFC product out of a FreeCAD object"""

    uid = ifcopenshell.guid.new()
    context = ifcfile[get_body_context_ids(ifcfile)[-1]] # TODO should this be different?
    history = get_ifc_element(parent).OwnerHistory # TODO should this be changed?
    name = obj.Label
    description = getattr(obj,"Description","")

    # use the Arch exporter
    import exportIFC
    import exportIFCHelper
    # setup exporter - TODO do that in the module init
    exportIFC.clones = {}
    exportIFC.profiledefs = {}
    exportIFC.surfstyles = {}
    exportIFC.ifcopenshell = ifcopenshell
    exportIFC.ifcbin = exportIFCHelper.recycler(ifcfile)
    ifctype = exportIFC.getIfcTypeFromObj(obj)
    prefs = exportIFC.getPreferences()
    representation, placement, shapetype = exportIFC.getRepresentation(ifcfile, context, obj, preferences=prefs)
    product = exportIFC.createProduct(ifcfile, obj, ifctype, uid, history, name, description, placement, representation, prefs)
    return product


def create_relationship(obj, parent, element, ifcfile):

    """Creates a relationship between an IFC object and a parent IFC object"""

    parent_element = get_ifc_element(parent)

    # remove any existing rel
    uprels = parent_element.IsDecomposedBy
    rels = element.Decomposes
    if rels:
        for rel in rels:
            if element in rel.RelatedObjects:
                print("DEBUG: Element",element,"is part of",rel.RelatingObject,"- removing")
                if len(rel.RelatedObjects) == 1:
                    # delete uprel if only contains our element
                    cmd = 'root.remove_product'
                    ifcopenshell.api.run(cmd, ifcfile, product=rel)
                else:
                    # delete this element from these uprels
                    cmd = 'attribute.edit_attributes'
                    attribs = {"RelatedObjects": [o for o in rel.RelatedObjects if o != element]}
                    ifcopenshell.api.run(cmd, ifcfile, product=rel, attributes=attribs)
    # add to existing relationship if possible
    if uprels:
        for uprel in uprels:
            if element in uprel.RelatedObjects:
                # element already related to parent
                break
        else:
            uprel = uprels [0] # We take arbitrarily the first one. TODO is that adequate?
            cmd = 'attribute.edit_attributes'
            attribs = {"RelatedObjects": uprel.RelatedObjects + (element,)}
            ifcopenshell.api.run(cmd, ifcfile, product=uprel, attributes=attribs)
    else:
        # create aggregation
        history = parent_element.OwnerHistory
        uprel = ifcfile.createIfcRelAggregates(ifcopenshell.guid.new(), history, None, None, parent_element, [element])
    parent.addObject(obj)
    return uprel


def get_elem_attribs(ifcentity):

    # usually info_ifcentity = ifcentity.get_info() would de the trick
    # the above could raise an unhandled excption on corrupted ifc files in IfcOpenShell
    # see https://github.com/IfcOpenShell/IfcOpenShell/issues/2811
    # thus workaround

    info_ifcentity = {
        "id": ifcentity.id(),
        "type": ifcentity.is_a()
    }

    # get attrib keys
    attribs = []
    for anumber in range(20):
        try:
            attr = ifcentity.attribute_name(anumber)
        except Exception:
            break
        # print(attr)
        attribs.append(attr)

    # get attrib values
    for attr in attribs:
        try:
            value = getattr(ifcentity, attr)
        except Exception as e:
            # print(e)
            value = "Error: {}".format(e)
            print(
                "DEBUG: The entity #{} has a problem on attribut {}: {}"
                .format(ifcentity.id(), attr, e)
            )
        # print(value)
        info_ifcentity[attr] = value

    return info_ifcentity
