// Time-related utilities and sleep calculation functions

export function nowIso() {
    return new Date().toISOString();
}

// Helper to format elapsed time
export function formatElapsedTime(timestampMs) {
    const elapsed = Math.floor((Date.now() - timestampMs) / 1000 / 60);
    const hours = Math.floor(elapsed / 60);
    const mins = elapsed % 60;
    return hours > 0 ? `${hours}h ${mins}m ago` : `${mins}m ago`;
}

// Helper to create day boundary timestamps
function getDayBounds(date) {
    // Create start/end in local timezone - these are Date objects representing
    // midnight and end-of-day in the local timezone
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);
    const end = new Date(date.getFullYear(), date.getMonth(), date.getDate(), 23, 59, 59, 999);
    // Return ISO strings for database queries - these will be in UTC but represent
    // the local day boundaries
    return { start: start.toISOString(), end: end.toISOString() };
}

// Helper to get day bounds as Date objects (not ISO strings)
export function getDayBoundsAsDate(date) {
    const { start, end } = getDayBounds(date);
    return { dayStart: new Date(start), dayEnd: new Date(end) };
}

// Helper to check if an entry is within day boundaries
export function isEntryInDay(entry, dayStart, dayEnd) {
    const ts = new Date(entry.ts);
    return ts >= dayStart && ts <= dayEnd;
}

// Helper to filter entries to only those within the day
export function filterEntriesInDay(entries, date) {
    const { dayStart, dayEnd } = getDayBoundsAsDate(date);
    return entries.filter(e => isEntryInDay(e, dayStart, dayEnd));
}

// Helper to find last sleep start entry
export function findLastSleepStart(entries) {
    return [...entries]
        .reverse()
        .find(e => e.type === "sleep" && (e.value === "sleeping" || e.value === "nap"));
}

// Helper to check if an entry represents sleep
export function isSleepEntry(entry) {
    return entry.type === "sleep" && (entry.value === "sleeping" || entry.value === "nap");
}

// Helper to check if an entry represents being awake
export function isAwakeEntry(entry) {
    return entry.type === "sleep" && entry.value === "awake";
}

// Process sleep events for a given day with proper boundary handling
export function processSleepEventsForDay(entries, dayStart, dayEnd) {
    // Filter out deleted entries and get sleep events
    const activeEntries = entries.filter(e => !e.deleted);
    let sleepEvents = activeEntries.filter((e) => e.type === "sleep");
    
    // Determine initial state (awake by default if no prior sleep event)
    const preDaySleepEvents = sleepEvents.filter(e => new Date(e.ts) < dayStart);
    const lastPreDayEvent = preDaySleepEvents.length > 0 ? 
        preDaySleepEvents[preDaySleepEvents.length - 1] : null;
    const startAsleep = lastPreDayEvent && isSleepEntry(lastPreDayEvent);
    
    // Add mock event at day start
    if (startAsleep) {
        sleepEvents = [
            { type: "sleep", value: "sleeping", ts: dayStart.toISOString(), mock: true },
            ...sleepEvents
        ];
    } else {
        sleepEvents = [
            { type: "sleep", value: "awake", ts: dayStart.toISOString(), mock: true },
            ...sleepEvents
        ];
    }
    
    // Add mock event at day end based on current state
    const inDaySleepEvents = sleepEvents.filter(e => {
        const ts = new Date(e.ts);
        return ts >= dayStart && ts <= dayEnd;
    });
    if (inDaySleepEvents.length > 0) {
        const lastInDayEvent = inDaySleepEvents[inDaySleepEvents.length - 1];
        const endAsleep = isSleepEntry(lastInDayEvent);
        if (endAsleep) {
            sleepEvents.push({ type: "sleep", value: "awake", ts: dayEnd.toISOString(), mock: true });
        }
    }
    
    return sleepEvents;
}

// Merge consecutive sleep windows (sleep followed by sleep)
export function mergeConsecutiveSleepEvents(sleepEvents) {
    const mergedSleepEvents = [];
    for (let i = 0; i < sleepEvents.length; i++) {
        const event = sleepEvents[i];
        if (isSleepEntry(event)) {
            // Check if next event is also a sleep start
            const nextEvent = sleepEvents[i + 1];
            if (nextEvent && isSleepEntry(nextEvent)) {
                // Skip this sleep end / next sleep start pair
                continue;
            }
        }
        mergedSleepEvents.push(event);
    }
    return mergedSleepEvents;
}

// Calculate total sleep duration for a day
export function calculateSleepDuration(sleepEvents, dayStart, dayEnd, currentReportDate) {
    let totalSleepMinutes = 0;
    let currentSleepStart = null;

    sleepEvents.forEach((event, i) => {
        if (isSleepEntry(event)) {
            currentSleepStart = new Date(event.ts);
        } else if (isAwakeEntry(event) && currentSleepStart) {
            const awakeTime = new Date(event.ts);
            
            // Clip sleep period to the current day's boundaries
            const clippedStart = currentSleepStart < dayStart ? dayStart : currentSleepStart;
            const clippedEnd = awakeTime > dayEnd ? dayEnd : awakeTime;
            
            // Only count if the clipped period is within the day
            if (clippedEnd > clippedStart) {
                const duration = (clippedEnd - clippedStart) / 1000 / 60;
                totalSleepMinutes += duration;
            }
            currentSleepStart = null;
        }
    });
    
    // Handle ongoing sleep that hasn't ended yet
    if (currentSleepStart) {
        const now = new Date();
        const reportDate = currentReportDate;
        const isToday = reportDate.toDateString() === now.toDateString();
        
        if (isToday) {
            // Clip to current time if viewing today
            const clippedStart = currentSleepStart < dayStart ? dayStart : currentSleepStart;
            const clippedEnd = now > dayEnd ? dayEnd : now;
            
            if (clippedEnd > clippedStart) {
                const duration = (clippedEnd - clippedStart) / 1000 / 60;
                totalSleepMinutes += duration;
            }
        } else {
            // For past days, assume sleep continued until end of day
            const clippedStart = currentSleepStart < dayStart ? dayStart : currentSleepStart;
            if (dayEnd > clippedStart) {
                const duration = (dayEnd - clippedStart) / 1000 / 60;
                totalSleepMinutes += duration;
            }
        }
    }

    const hours = Math.floor(totalSleepMinutes / 60);
    const minutes = Math.round(totalSleepMinutes % 60);
    return { hours, minutes, totalMinutes: totalSleepMinutes };
}

// Convert sleep events to timeline data for visualization
export function convertSleepEventsToTimelineData(sleepEvents, dayStart) {
    const lineData = [];
    sleepEvents.forEach((e) => {
        const date = new Date(e.ts);
        const hours = (date - dayStart) / (1000 * 60 * 60);
        const value = isSleepEntry(e) ? 1 : 0;
        if (hours >= 0 && hours <= 24) {
            lineData.push({ time: hours, value: value });
        }
    });
    return lineData;
}

// Process sleep attempts for display
export function processSleepAttempts(entries) {
    const activeEntries = entries.filter(e => !e.deleted);
    const sleepEvents = activeEntries.filter((e) => e.type === "sleep");

    const attempts = [];
    let currentAttempt = null;

    sleepEvents.forEach((event, i) => {
        if (isSleepEntry(event)) {
            if (currentAttempt) {
                attempts.push(currentAttempt);
            }
            currentAttempt = {
                start: new Date(event.ts),
                type: event.value,
                soothe: [],
            };
        } else if (isAwakeEntry(event) && currentAttempt) {
            currentAttempt.end = new Date(event.ts);
            const duration = (currentAttempt.end - currentAttempt.start) / 1000 / 60;
            currentAttempt.success = duration > 15; // More than 15 minutes = success
            attempts.push(currentAttempt);
            currentAttempt = null;
        }
    });

    if (currentAttempt) {
        currentAttempt.success = true; // Still sleeping
        attempts.push(currentAttempt);
    }

    return attempts;
}