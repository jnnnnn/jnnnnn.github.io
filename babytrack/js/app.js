// Main app entry point and coordination
import { initDB, addEntry, loadEntriesByDate, loadTodayEntries, markMostRecentAsDeleted, undeleteEntry, updateEntryTimestamp, nowIso, filterEntriesInDay } from './database.js';
import { renderButtons, updateButtonStates, updateTimestamp, getLongPressData, hideTimePicker } from './ui.js';
import { 
    setReportDate, 
    changeReportDate, 
    goToToday, 
    getCurrentReportDate,
    calculateDailyStats, 
    updateStatsDisplay, 
    updateHourlyGrid, 
    updateSleepAttempts, 
    updateRecentEvents, 
    drawTimeline 
} from './reports.js';
import { downloadCSV } from './export.js';
import { generateTestData } from './testdata.js';

// Main save function
export async function save(type, value, btn, customTimestamp = null) {
    const ts = customTimestamp || nowIso();
    const eventTime = new Date(ts);

    // Add animation
    if (btn) {
        btn.classList.add("fading");
        setTimeout(() => {
            btn.classList.remove("fading");
        }, 400);
    }

    // Auto-awake: if recording any non-sleep event, mark baby as awake first
    if (type !== "sleep") {
        const allEntries = await loadEntriesByDate();
        const lastSleepEvent = [...allEntries].reverse().find(e => e.type === "sleep" && !e.deleted);
        const isAsleep = lastSleepEvent && (lastSleepEvent.value === "sleeping" || lastSleepEvent.value === "nap");
        
        if (isAsleep) {
            // Add awake event just before this event (1 second earlier to maintain order)
            const awakeTs = new Date(eventTime.getTime() - 1000).toISOString();
            await addEntry("sleep", "awake", awakeTs);
        }
    }

    // Persist this single entry
    await addEntry(type, value, ts);

    updateTimestamp("Saved: " + eventTime.toLocaleTimeString());
    updateDailyReport();
    updateButtonStates(loadTodayEntries);
}

export async function saveWithCustomTime() {
    // Check if we're editing an existing entry
    if (window.editingEntryKey) {
        await updateEntryTime();
        return;
    }

    const input = document.getElementById("custom-time");
    const customTime = new Date(input.value);

    if (!customTime || isNaN(customTime.getTime())) {
        alert("Please select a valid time");
        return;
    }

    const longPressData = getLongPressData();
    if (!longPressData) return;
    
    const { type, value, btn } = longPressData;
    await save(type, value, btn, customTime.toISOString());
    hideTimePicker();
}

async function updateEntryTime() {
    const input = document.getElementById("custom-time");
    const newTime = new Date(input.value);

    if (!newTime || isNaN(newTime.getTime())) {
        alert("Please select a valid time");
        return;
    }

    const key = window.editingEntryKey;
    if (!key) return;

    await updateEntryTimestamp(key, newTime.toISOString());
    updateTimestamp("Time updated");
    updateDailyReport();
    updateButtonStates(loadTodayEntries);
    hideTimePicker();
    window.editingEntryKey = null;
}

export async function undo() {
    const result = await markMostRecentAsDeleted();

    if (result) {
        updateTimestamp("Marked as deleted");
        updateDailyReport();
        updateButtonStates(loadTodayEntries);
    }
}

export async function undelete() {
    // Find most recently deleted entry
    const allEntries = await loadEntriesByDate();
    const deletedEntries = allEntries.filter(e => e.deleted);
    
    if (deletedEntries.length === 0) {
        updateTimestamp("No deleted entries to restore");
        return;
    }
    
    // Sort by timestamp descending to get most recent
    deletedEntries.sort((a, b) => new Date(b.ts) - new Date(a.ts));
    const mostRecentDeleted = deletedEntries[0];
    
    await undeleteEntry(mostRecentDeleted.key);
    updateTimestamp("Entry restored");
    updateDailyReport();
    updateButtonStates(loadTodayEntries);
}

async function saveNote(e) {
    const v = e.target.value.trim();
    if (!v) return;
    await save("note", v);
    e.target.value = "";
}

export async function updateDailyReport() {
    const currentDate = getCurrentReportDate();
    const allEntries = await loadEntriesByDate(currentDate);
    
    // Filter to only entries within the current day for display purposes
    const entriesInDay = filterEntriesInDay(allEntries, currentDate);

    // Calculate statistics (uses allEntries for cross-midnight sleep)
    const stats = calculateDailyStats(allEntries);
    updateStatsDisplay(stats);
    
    // Display functions use filtered entries only
    updateHourlyGrid(entriesInDay);
    updateSleepAttempts(entriesInDay);
    updateRecentEvents(entriesInDay, updateDailyReport, () => updateButtonStates(loadTodayEntries));
    
    // Timeline needs allEntries to show cross-midnight sleep properly
    drawTimeline(allEntries);
}

// Global function wrappers for HTML onclick handlers
export function setReportDateWrapper(date) {
    setReportDate(date);
    updateDailyReport();
}

export function changeReportDateWrapper(days) {
    changeReportDate(days);
    updateDailyReport();
}

export function goToTodayWrapper() {
    goToToday();
    updateDailyReport();
}

export function downloadCSVWrapper() {
    downloadCSV(loadEntriesByDate);
}

export function generateTestDataWrapper() {
    generateTestData(addEntry).then(() => {
        updateDailyReport();
    });
}

// Initialize the app when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
    // Initialize date selector to today
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    document.getElementById("report-date").value = `${year}-${month}-${day}`;

    // Build hourly grid
    const hourlyGrid = document.getElementById("hourly-grid");

    // Add empty cell for top-left corner
    const corner = document.createElement("div");
    hourlyGrid.appendChild(corner);

    // Add hour labels across the top
    for (let hour = 0; hour < 24; hour++) {
        const label = document.createElement("div");
        label.className = "hour-label";
        label.textContent = hour;
        hourlyGrid.appendChild(label);
    }

    // Add rows with labels
    const rows = [
        { label: "Feed", type: "feed" },
        { label: "Sleep", type: "sleep" },
        { label: "Wet", type: "wet" },
        { label: "Dirty", type: "dirty" },
    ];

    rows.forEach((row) => {
        // Add row label
        const rowLabel = document.createElement("div");
        rowLabel.className = "row-label";
        rowLabel.textContent = row.label;
        hourlyGrid.appendChild(rowLabel);

        // Add indicators for each hour
        for (let hour = 0; hour < 24; hour++) {
            const indicator = document.createElement("div");
            indicator.className = `hour-indicator ${row.type}`;
            indicator.id = `hour-${hour}-${row.type}`;
            indicator.title = `${row.label} at ${hour}:00`;
            hourlyGrid.appendChild(indicator);
        }
    });

    // Initialize database and app
    initDB().then(() => {
        renderButtons();
        updateDailyReport();
        updateButtonStates(loadTodayEntries);
    });

    // Set up event listeners
    document.addEventListener("keydown", (e) => {
        if (
            e.key === "Enter" &&
            document.activeElement?.id === "notes"
        ) {
            saveNote({ target: document.activeElement });
        }
    });

    // Update button states every minute to keep elapsed times current
    setInterval(() => {
        updateButtonStates(loadTodayEntries);
    }, 60000); // 60000ms = 1 minute
});

// Make functions available globally for HTML onclick handlers
window.save = save;
window.saveWithCustomTime = saveWithCustomTime;
window.undo = undo;
window.undelete = undelete;
window.downloadCSV = downloadCSVWrapper;
window.setReportDate = setReportDateWrapper;
window.changeReportDate = changeReportDateWrapper;
window.goToToday = goToTodayWrapper;
window.hideTimePicker = hideTimePicker;
window.generateTestData = generateTestDataWrapper;