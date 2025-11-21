# Activity Tracker

A flexible, configurable tracking application that can be adapted for various use cases including baby care, warehouse management, lab experiments, and more.

## Features

- **Configurable Interface**: Customize tracking categories, buttons, and behavior through a JSON configuration
- **Stateful Groups**: Track state changes (e.g., sleeping/awake, equipment on/off) with automatic duration calculation
- **Counted Events**: Count occurrences of specific events with daily totals
- **Historical Data**: View and analyze data by date with interactive graphs and statistics
- **Data Export**: Download tracking data as CSV
- **Offline Support**: All data stored locally in IndexedDB
- **Undo/Redo**: Full undo/redo support for all actions

## Getting Started

1. Open `babytrack.html` in a modern web browser
2. Click the settings gear (⚙️) in the top-right corner to configure your tracking needs
3. Choose a template (Baby, Warehouse, Lab) or create your own custom configuration
4. Start tracking by clicking the buttons!

## Configuration

The app uses a JSON configuration structure:

```json
{
  "title": "Your Tracker Title",
  "groups": [
    {
      "name": "Group Name",
      "stateful": false,
      "counted": true,
      "buttons": [
        {
          "type": "event_type",
          "value": "event_value",
          "label": "Button Label",
          "emoji": "📦",
          "counted": true
        }
      ]
    }
  ]
}
```

### Configuration Options

- **title**: The main title displayed in the app
- **groups**: Array of button groups

#### Group Properties

- **name**: Display name for the group
- **stateful**: (boolean) If true, treats buttons as state transitions (e.g., on/off, sleeping/awake)
  - Tracks duration in each state
  - Highlights the current state
  - Shows state sessions in the graphs tab
- **counted**: (boolean) If true, shows daily count for all events in this group

#### Button Properties

- **type**: Event type (used for database storage and filtering)
- **value**: Event value (the specific state or action)
- **label**: Display text on the button
- **emoji**: Optional emoji to display on graphs (default: "•")
- **counted**: (boolean) Optional, shows daily count for this specific button (even if group is not counted)

## Templates

### Baby Template
Tracks feeding, sleeping, diaper changes, and soothing techniques for infant care.

### Warehouse Template
Tracks receiving, shipping, and operational status for warehouse management.

### Lab Template
Tracks equipment status, sample processing, and observations for laboratory work.

## Data Storage

- Configuration is stored in `localStorage` and persists across sessions
- Event data is stored in IndexedDB as "ActivityTrackerDB"
- All data remains on your device (no cloud sync)

## Tips

- **Long Press**: Long-press any button to set a custom timestamp for an event
- **Undo**: The Undo button will delete the most recent entry if no other actions are in the undo stack
- **Filtering**: Use the event log filters to search and filter by event type
- **Export**: Download CSV files with date filtering for external analysis

## Browser Compatibility

Requires a modern browser with support for:
- IndexedDB
- LocalStorage
- ES6 JavaScript
- CSS Grid

Tested on Chrome, Firefox, Edge, and Safari.
