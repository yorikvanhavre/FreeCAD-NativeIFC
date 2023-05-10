# NativeIFC documentation

This is the documentation of the NativeIFC addon. It is made a of a series of common BIM tasks, and explains simply how to perform each of them with the NativeIFC addon.

### Table of contents

* [Introduction](#introduction)
* [Enabling NativeIFC](#enabling-nativeifc)
* [Import an IFC file](#import-an-ifc-file)
* [Expand sub-objects of an IFC object](#expand-sub-objects-of-an-ifc-object)
* [Load the shape of an IFC object](#load-the-shape-of-an-ifc-object)
* [Change IFC attributes](#change-ifc-attributes)
* [See the changes in an IFC document](#see-the-changes-in-an-ifc-document)
* [Saving the modified IFC file](#saving-the-modified-ifc-file)
* [Add a new IFC document](#add-a-new-ifc-document)
* [Modifying the IFC type of an object](#modifying-the-ifc-type-of-an-object)
* [Inspecting the IFC structure of an object](#inspecting-the-ifc-structure-of-an-object)
* [Add a new model structure](#add-a-new-model-structure)
* [Add a new object](#add-a-new-object)
* [Change the schema of an IFC document](#change-the-schema-of-an-ifc-document)
* [Create 2D drawings (plans, sections) from an IFC file](#create-2d-drawings-plans-sections-from-an-ifc-file)

### Introduction

The NativeIFC addon is designed to allow you to work on IFC file in FreeCAD natively. 

The traditional way most BIM applications work with IFC files consists of loading the file, translating its contents into the application's own format, then letting you work with the model. When saving back to IFC, another translation is done between the application's format and the IFC format. That's two translation operatins each time you need to work on the file. This brings huge imprevisibility and a lot of data loss.

The Native IFC concept, on the other way, considers the IFC file as the only source of truth. Loading an IFC file into FreeCAD merely shows you the contents of the IFC file in the FreeCAD interface and 3D view. Any operation made on those contents is directly affecting the contents of the IFC file. When saving the file, only what you have modified will have changed in the IFC file.

This allows a lot more control over what changes in different stages of the life of an IFC file, and turns it truly and fully versionable.with systems like [Git](https://git-scm.com/). FreeCAD is the second BIM application that supports NativeIFC, after [BlenderBIM](https://blenderbim.org).

Working with native IFC files in FreeCAD is simple: Open an existing IFC file or create a new project using the project tool from the BIM workbench. Create new objects with any of the FreeCAD workbenches or tools. Add these objects to your IFC project by dragging them into the project structure. Save the file, and you are done!

### Enabling NativeIFC

* Install the addon as described in the [installation page](installation.md)
* Also install the BIM workbench addon to be able to create new IFC projects
* Restart FreeCAD

### Import an IFC file

#### From the UI

* From menu `File` → `Open` or `File` → `Insert`: choose an IFC file, choose the **NativeIFC** importer
* From the start page: set "ifc_import" as a [default importer for IFC files](https://wiki.freecad.org/Fine-tuning#Specific_Workbenches), then just click an IFC file
![example workflow](images/workflow01.jpg)
* Set the desired options. For large files, creating one root object only and no shapes (coin representatipon only) is the fastest way. Objects can have their children and shapes expanded later, as needed. A "no representation" mode is also available, which will load the IFC file structure in the tree, but no 3D representation is created
![example workflow](images/workflow08.jpg)
* A FreeCAD document is created
* An object is created representing the IFC root document + project
![example workflow](images/workflow02.jpg)

#### From Python

```python
import ifc_import
ifc_import.open(filepath) # or ifc_import.insert(fileapth,document)
```

### Expand sub-objects of an IFC object

#### From the UI
 
* Right-click any IFC object on the tree and select **Expand children**
![example workflow](images/workflow03.jpg)
* A site object, or any other child object is created. You can further expand those children, until there is no more child
![example workflow](images/workflow04.jpg)

#### From Python

```python
import ifc_tools
ifc_tools.create_children(myObject,[recursive=True/False])
```

### Load the shape of an IFC object

#### From  the UI 

Right-click the object in the tree -> load shape

#### From Python

```python
myObject.ShapeMode = "Shape"
myObject.Document.recompute()
```

### Change IFC attributes

#### From the UI

Change values like name, description... directly from the object's properties
![example workflow](images/workflow05.jpg)

#### From Python

```python
myObject.Label = "My New Name"
myObject.Description = "A very nice object"
```

### See the changes in an IFC document

#### From the UI

* Right-click a modified IFC project object in the tree view
* Select "View diff..."
* A dialog window pops up showing the modified lines since last saved version

#### From Python

```python
import ifc_diff
# get an existing IFC document object by its name
project = FreeCAD.ActiveDocument.getObject("IfcObject")
ifc_diff.get_diff(project)
```

### Saving the modified IFC file

#### From the UI

* When any attribute of an object in an IFC document has changed, the icon of the IFC document object shows a red dot, and a **save** option becomes available when right-clicking it
* Manually: Right-click the project object in the tree -> Save or Save as
![example workflow](images/workflow06.jpg)
* After saving, only the changed parameters have changed in the linked IFC file
![example workflow](images/workflow07.jpg)
* Automatically: Save the FreeCAD document

#### From Python

```python
import ifc_tools
ifc_tools.save(myProject,[filepath=/path/to/somefile.ifc])
```

### Add a new IFC document

#### From the UI

Use the **Project** tool from the BIM workbench

#### From Python

```python
import ifc_tools
doc = FreeCAD.ActiveDocument
ifc_tools.create_document(doc)
```

### Modifying the IFC type of an object

#### From the UI

Change the type directly from the object's properties

#### From Python

```python
myObject.Type = "IfcWall"
```

### Inspecting the IFC structure of an object

#### From the UI

Right-click any object in the tree, and choose **Show geometry tree**

#### From Python

```python
import ifc_tools
import ifc_tree
element = ifc_tools.get_ifc_element(myObject)
ifc_tree.print_geometry_tree(element) # this prints text, or
tree_list = ifc_tree.get_geometry_tree(element) # this returns a list
```

### Add a new model structure

#### From the UI

* Switch to the BIM workbench
* Create a Project object
* Create a Site object
* Drag the site onto the project
* Create a Building object
* Drag the building onto the site
* Create a Level object
* Drag the level onto the building

#### From Python

```python
import ifc_tools
import Arch
doc = FreeCAD.ActiveDocument
project = ifc_tools.create_document(doc)
site = Arch.makeSite()
site = ifc_tools.aggregate(site, project)
building = Arch.makeBuilding()
building = ifc_tools.aggregate(building, site)
level = Arch.makeFloor()
level = ifc_tools.aggregate(floor, building)
```

### Add a new object

#### From the UI

* Create any desired object with other FreeCAD tools, ex. a wall with the BIM workbench
* In the tree view, drag that wall onto an IFC project object or a building structure element (Building, storey,...)

#### From Python

```python
# create an object with any other workbench
import Arch
wall = Arch.makeWall(220,400,20)
# get an existing IFC document object by its name
project = FreeCAD.ActiveDocument.getObject("IfcObject")

import ifc_tools
ifc_tools.aggregate(wall, project)
```

### Change the schema of an IFC document

#### From the UI

Change the 'Schema' property of the object

#### From Python

```python
myProject.Schema = "IFC4"
```

### Create 2D drawings (plans, sections) from an IFC file

#### From the UI

* Make sure all the objects you need to see have their shape loaded
* Select all the objects to be cut or viewed
* Create a [section plane](https://wiki.freecad.org/Arch_SectionPlane)
* Optionally, rotate the section plane into desired position, using the [Rotate](https://wiki.freecad.org/Draft_Rotate) tool or double-clicking the section plane in the tree and using the available calibration tools
* Optionally, move the section plane into desired position using the [Move](https://wiki.freecad.org/Draft_Move) tool
* Create a [Shape view](https://wiki.freecad.org/Draft_Shape2DView) of the section plane. Move it into desired position
* Optionally, to show cut lines, create a second Shape view, set its projection mode to **Cut Lines**, set its line width a bit higher, and move it to the same position as the first one
* This view can now be annotated using Draft tools
* This view and its annotations can be exported to DXF/DWG using File -> Export
* This view and its annotations can be added to a printable page using the [TechDraw Workbench](https://wiki.freecad.org/TechDraw_Workbench)
![example workflow](images/workflow09.jpg)


### To be documented

* [ ] **Modify the shape of an element**
* [ ] **Extracting quantities from an IFC file**
* [ ] **Creating renderings of an IFC file**
