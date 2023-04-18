## NativeIFC addon for FreeCAD

This is a preliminary stub to integrate [BlenderBIM](https://blenderbim.org) into [FreeCAD](https://freecad.org). The final goal is to offer in FreeCAD the same level of functionality found in BlenderBIM, mainly the native handling of IFC files, which means the data manipulation in FreeCAD is affecting directly the IFC model.

Check for updates on this project at https://yorik.uncreated.net/blog/nativeifc

### Roadmap

#### 1. Get a working concept up

* [x] Write an importer that allows an initial import of an IFC file into FreeCAD
* [x] Write a custom parametric FreeCAD object that represents an IFC document in the FreeCAD tree
* [x] Do an initial geometry import
* [x] Write a custom parametric FreeCAD object that represents in IFC product in the FreeCAD tree
* [x] Reveal the document structure in the FreeCAD tree
* [x] Allow an object shape to be built automatically from its children
* [x] Allow to expand a document (reveal its children)
* [x] Use group extension
* [x] Support colors

#### 2. Allow basic editing

* [x] Use enums in enum-based properties
* [ ] ~~Fetch attribute documentation~~ canceled for now because it yields too much text
* [x] Fetch context-dependent IFC types
* [x] Find a way to not store the whole enum in the file
* [x] Add progress feedback
* [x] Allow to change an attribute of an object
* [x] Allow to manually save the linked IFC file
* [x] Implement mesh mode
* [x] Allow different storage strategies (full shape or only coin representation)
* [x] Write a hook system that allows FreeCAD to save the IFC document
* [x] Test (and solve!) what happens when opening a NativeIFC file in vanilla FreeCAD
* [x] Add a shape caching system
* [x] Tie the shape caching to the corresponding IFC document
* [x] Allow to change the class of an object
* [x] Allow late loading/rebuilding of coin representation

#### 3. Allow adding and removing objects

* [x] Allow different import strategies (full model, only building structure...)
* [x] Allow to create an IFC document without an existing IFC file
* [x] Allow to add building structure (building, storey...)
* [x] Allow to add a simple generic IFC product
* [x] Allow to delete objects
* [x] Allow to hide children of an object
* [ ] Tie all of the above to BIM commands

#### 4. Allow advanced editing

* [x] Allow to edit placements
* [ ] Define a strategy for expanding non-IfcProduct elements
* [ ] Expand attributes
* [ ] Expand materials
* [ ] Expand properties
* [ ] Allow to regroup elements
* [x] Handle drag/drop
* [ ] Handle undo/redo
* [x] Allow to change the IFC schema

#### 5. Tie NativeIFC and BIM Workbenches

* [ ] Support walls
* [ ] Support structures
* [ ] Support windows
* [ ] Support 2D entitties
* [ ] Support dimensions
* [ ] Support Part extrusions
* [ ] Support Part booleans

#### Additionals

* [ ] Add this to the addons manager
* [ ] Add to BIM WB dependencies/ reorganize addon
* [ ] Verify and adapt 2D view generation workflow
* [ ] Verify and adapt quantifying workflow
* [ ] Document everything
* [ ] Upstream all pure ifcopenshell functionality to ifcopenshell.utils
* [ ] Transfer Arch exportIFC.getRepresentation() functionality to ifcopenshell.api.geometry


### Documentation

* [Installing](doc/installation.md)
* [Usage](doc/README.md)
* [IfcOpenShell documentation links](doc/links.md)
* [IfcOpenShell code examples](doc/code_examples.md)


### Performance

| File                                                                                                                                                    | File size | Import time (shape) | Import time (coin) | BlenderBIM |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ------------------- | ------------------ | ---------- |
| [IfcOpenHouse](https://github.com/aothms/IfcOpenHouse)                                                                                                  | 0.1Mb     | < 1s                | < 1s               | < 1s       |
| [AC20 FCK Haus](https://www.ifcwiki.org/images/e/e3/AC20-FZK-Haus.ifc)                                                                                  | 2.6Mb     | 2s                  | 1s                 | 1s         |
| [Schultz residence](https://github.com/OpeningDesign/Schultz_Residence/tree/master/Model)                                                               | 22Mb      | 27s                 | 6s                 | 5s         |
| [King Street simplified](http://www.simaud.org/datasets/)                                                                                               | 26Mb      | 1m17s               | 34s                | 14s        |
| [Schependomlaan](https://github.com/buildingSMART/Sample-Test-Files/blob/master/IFC%202x3/Schependomlaan/Design%20model%20IFC/IFC%20Schependomlaan.ifc) | 49Mb      | 21s                 | 6s                 | 5s         |
| [King Street full](http://www.simaud.org/datasets/)                                                                                                     | 155Mb     | Fails               | 46s                | 36s        |
| [Nineteen plots](https://forum.freecadweb.org/viewtopic.php?style=1&p=646935&sid=464a4dcd0f99a5903c749df51f3e73b0#p646935)                              | 4.3Mb     | 40s                 | 10s                | 4s         |

### Sponsors

This project is sponsored by:

[![](doc/images/otfn-logo.png)](https://opentoolchain-foundation.org/)
