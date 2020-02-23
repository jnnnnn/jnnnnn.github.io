# QuickGraph

This is a tool for quickly producing directed graph diagrams at maximum speed.

## Keys

| Key               | Effect                                        |
| ----------------- | --------------------------------------------- |
| n                 | Create a new node                             |
| e                 | Edit a node                                   |
| +/-               | Make nodes bigger or smaller                  |
| l/u               | Link / unlink nodes (from selection to mouse) |
| Shift + L         | Link with text                                |
| f                 | Make node fixed position (pinned)             |
| s/click           | Select a node (or clear selection)            |
| (Shift) backspace | Delete a(ll) node(s)                          |
| Ctrl(Shift)Z      | Undo (Redo)                                   |
| r                 | Reset view                                    |
| Shift + R         | Briefly reheat the simulation                 |
| c                 | Enter (or exit) **Command Mode**              |
| p                 | Toggle "Present" mode                         |
| Shift + F         | Arrows to new nodes point forward             |

For full details, see [commands.js](./modules/commands.js)

## Saving and Loading

The current diagram is saved to the page's localStorage.

You can export a json file of the diagram using Ctrl+S, and load from a file by dragging-and-dropping the file onto the diagram.

## Command Mode

In Command Mode, you can perform several actions using just the keyboard:

- Type a node's number followed by the Enter key to select it.
- Use the `link`, `unlink`, and `Link with text` commands by selecting a second
  node and pressing Enter when the node you want to link to is selected.
