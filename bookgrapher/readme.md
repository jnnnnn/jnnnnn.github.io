This is a tool for quickly producing concept diagrams at maximum speed.

## Keys

| Key                 | Effect                                        |
| ------------------- | --------------------------------------------- |
| e (mouse over node) | Create (edit) nodes' text                     |
| +/-                 | Make nodes bigger or smaller                  |
| l/u                 | Link / unlink nodes (from selection to mouse) |
| f                   | Make node fixed position (pinned)             |
| s/click             | Select a node (or clear selection)            |
| (Shift)d/backspace  | Delete a(ll) node(s)                          |
| Ctrl(Shift)Z        | Undo (Redo)                                   |
| r                   | Reset view                                    |

For full details, see [commands.js](./modules/commands.js)

## Saving and Loading

The current diagram is saved to the page's localStorage.

You can export a json file of the diagram using Ctrl+S, and load from a file by dragging-and-dropping the file onto the diagram.
