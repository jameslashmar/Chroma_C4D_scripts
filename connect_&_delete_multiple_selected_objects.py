import c4d
from c4d import gui

# Main function
def main():
    doc.StartUndo()  # Start recording undos

    selection = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_CHILDREN)  # Get the selected objects

    if not selection:
        gui.MessageDialog("No objects selected.")
        return

    for obj in selection:
        doc.AddUndo(c4d.UNDOTYPE_DELETE, obj)  # Record for undo

        # If the object is an Extrude object, make it editable first
        if obj.GetType() == c4d.Oextrude:
            # Make a copy of the Extrude object and insert it into the document
            temp_extrude = obj.GetClone()
            temp_extrude[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = c4d.OBJECT_OFF
            temp_extrude[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF
            doc.InsertObject(temp_extrude)
            doc.AddUndo(c4d.UNDOTYPE_NEW, temp_extrude)

            # Select the copy and make it editable
            doc.SetActiveObject(temp_extrude)
            c4d.CallCommand(12236)  # Make Editable

            # Get the resulting polygon object
            poly_obj = doc.GetActiveObject()
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, poly_obj)
        else:
            # Directly use non-Extrude objects
            poly_obj = obj

        # Proceed to connect and delete
        if poly_obj:
            # Store the original matrix and name
            original_matrix = poly_obj.GetMg()
            original_name = poly_obj.GetName()

            # Perform 'Connect and Delete' on the polygon object
            doc.SetActiveObject(poly_obj)
            c4d.CallCommand(16768)  # Connect Objects + Delete

            # Get the new object and set its transformation and name
            new_obj = doc.GetActiveObject()
            if new_obj:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, new_obj)
                new_obj.SetMg(original_matrix)
                new_obj.SetName(original_name)

                # Insert the new object at the same place as the old one
                new_obj.Remove()
                doc.InsertObject(new_obj, parent=obj.GetUp(), pred=obj.GetPred())

        # Remove the original object
        obj.Remove()

    doc.EndUndo()  # End recording undos
    c4d.EventAdd()  # Update Cinema 4D

# Execute main()
if __name__=='__main__':
    main()
