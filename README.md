# BlenderBIM addon for FreeCAD

This is a preliminary stub to integrate [BlenderBIM](https://blenderbim.org) 
into FreeCAD. The final goal is to offer in FreeCAD the same level of 
functionality found in BlenderBIM.

### The plan

#### 1. Get a working concept up (no geometry just yet)

* [x] Write an importer that allows an initial import of an IFC file into FreeCAD
* [x] Write a custom parametric FreeCAD object that represents an IFC document in the FreeCAD tree
* [ ] Write a custom parametric FreeCAD object that represents in IFC product in the FreeCAd tree
* [ ] Allow to expand a document (reveal its children in FreeCAD in the FreeCAD tree)
* [ ] Write a hook system that allows FreeCAD to save the IFC document
* [ ] Test what happens when opening a bb file in vanilla FreeCAD

### Installation & Usage

#### To install

* Navigate to your FreeCAD Mods folder (~/.local/share/FreeCAD/Mods)
* Clone this repo there: `git clone https://github.com/yorikvanhavre/FreeCAD-BlenderBIM.git`

#### To test

* Run FreeCAD
* File -> Open or File -> Insert, select an IFC file
* Select the BlenderBIM importer (bb_import)
* A FreeCAD document is created
* An object is created representing the IFC root document + project

### Notes

#### Documentation

* [IfcOpenShell github](https://github.com/IfcOpenShell/IfcOpenShell)
* [BlenderBIM ifcOpenShell docs](https://blenderbim.org/docs/)

#### Code examples

Initial import + getting the main file structure

```python
import ifcopenshell
f = ifcopenshel.open("IfcOpenHouse.ifc")
p = f.by_type("IfcProject")[0]
# get descendents (site, building, and everything inside)
d = ifcopenshell.util.element.get_decomposition(p)
```

Other functions:

**get_aggregate()**

    Retrieves the aggregate of an element.
    
    :param element: The IFC element
    :return: The aggregate of the element
    
    Example::
    element = file.by_type("IfcBeam")[0]
    aggregate = ifcopenshell.util.element.get_aggregate(element)

**get_container()**

    Retrieves the spatial structure container of an element.
    
    :param element: The IFC element
    :type element: ifcopenshell.entity_instance.entity_instance
    :param should_get_direct: If True, a result is only returned if the element
        is directly contained in a spatial structure element. If False, an
        indirect spatial container may be returned, such as if an element is a
        part of an aggregate, and then if that aggregate is contained in a
        spatial structure element.
    :type should_get_direct: bool
    :return: The direct or indirect container of the element or None.
    
    Example::
    
        element = file.by_type("IfcWall")[0]
        container = ifcopenshell.util.element.get_container(element)

**get_decomposition()**

    Retrieves the decomposition of an element.
    
    :param element: The IFC element
    :return: The decomposition of the element
    
    Example::
    
        element = file.by_type("IfcProject")[0]
        decomposition = ifcopenshell.util.element.get_decomposition(element)

**get_elements_by_material()**

    Retrieves the elements related to a material.
    
    :param ifc_file: The IFC file
    :param material: The IFC Material entity
    :return: The elements related to the material
    
    Example::
    material = file.by_type("IfcMaterial")[0]
    elements = ifcopenshell.util.element.get_elements_by_material(file, material)

**get_elements_by_representation()**

**get_elements_by_style()**

    Retrieves the elements related to a style.
    
    :param ifc_file: The IFC file
    :param style: The IFC Style entity
    :return: The elements related to the style
    
    Example::
    style = file.by_type("IfcSurfaceStyle")[0]
    elements = ifcopenshell.util.element.get_elements_by_style(file, style)

**get_layers()**

**get_material()**

**get_parts()**

    Retrieves the parts of an element.
    
    :param element: The IFC element
    :return: The parts of the element
    
    Example::
    element = file.by_type("IfcElementAssembly")[0]
    parts = ifcopenshell.util.element.get_parts(element)

**get_predefined_type()**

    Retrieves the PrefefinedType attribute of an element.
    
    :param element: The IFC Element entity
    :return: The predefined type of the element
    
    Example::
    element = ifcopenshell.by_type("IfcWall")[0]
    predefined_type = ifcopenshell.util.element.get_predefined_type(element)

**get_properties()**

**get_property_definition()**

**get_psets()**

    Retrieve property sets, their related properties' names & values and ids.
    
    :param element: The IFC Element entity
    :param psets_only: Default as False. Set to true if only property sets are needed.
    :param qtos_only: Default as False. Set to true if only quantities are needed.
    :param should_inherit: Default as True. Set to false if you don't want to inherit property sets from the Type.
    :return: dictionnary: key, value pair of psets' names and their properties' names & values
    
    Example::
        element = ifcopenshell.by_type("IfcBuildingElement")[0]
        psets = ifcopenshell.util.element.get_psets(element, psets_only=True)
        qsets = ifcopenshell.util.element.get_psets(element, qtos_only=True)
        psets_and_qtos = ifcopenshell.util.element.get_psets(element)

**get_quantities()**

**get_referenced_structures()**

    Retreives a list of referenced structural elements
    
    :param element: The IFC element
    :type element: ifcopenshell.entity_instance.entity_instance
    
    Example::
    
        element = file.by_type("IfcWall")[0]
        print(ifcopenshell.util.element.get_referenced_structures(element))

**get_type()**

    Retrieves the Element Type entity related to an element entity.
    
    :param element: The IFC Element entity
    :return: The Element Type entity defining the element
    
    Example::
    element = ifcopenshell.by_type("IfcWall")[0]
    element_type = ifcopenshell.util.element.get_type(element)

**get_types()**
