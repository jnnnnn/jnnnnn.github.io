import { getDayBoundsAsDate, isEntryInDay, filterEntriesInDay, markEntryAsDeleted, undeleteEntry } from './database.js';
import { editEntryTime } from './ui.js';

// Daily Report Functions
let currentReportDate = new Date();

export function setReportDate(date) {
    // Parse date string as local date, not UTC
    if (typeof date === 'string') {
        const parts = date.split('-');
        currentReportDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    } else {
        currentReportDate = new Date(date);
    }
}

export function getCurrentReportDate() {
    return currentReportDate;
}

export function changeReportDate(days) {
    currentReportDate.setDate(currentReportDate.getDate() + days);
    // Format date as YYYY-MM-DD for the date input
    const year = currentReportDate.getFullYear();
    const month = String(currentReportDate.getMonth() + 1).padStart(2, '0');
    const day = String(currentReportDate.getDate()).padStart(2, '0');
    document.getElementById("report-date").value = `${year}-${month}-${day}`;
}

export function goToToday() {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    setReportDate(`${year}-${month}-${day}`);
}

export function calculateDailyStats(entries) {
    // Filter out deleted entries
    const activeEntries = entries.filter(e => !e.deleted);
    
    // Get day boundaries for clipping sleep periods
    const { dayStart, dayEnd } = getDayBoundsAsDate(currentReportDate);
    
    // Get sleep events and add mock events at day boundaries
    let sleepEvents = activeEntries.filter((e) => e.type === "sleep");
    
    // Determine initial state (awake by default if no prior sleep event)
    const preDaySleepEvents = sleepEvents.filter(e => new Date(e.ts) < dayStart);
    const lastPreDayEvent = preDaySleepEvents.length > 0 ? 
        preDaySleepEvents[preDaySleepEvents.length - 1] : null;
    const startAsleep = lastPreDayEvent && 
        (lastPreDayEvent.value === "sleeping" || lastPreDayEvent.value === "nap");
    
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
        const endAsleep = lastInDayEvent.value === "sleeping" || lastInDayEvent.value === "nap";
        if (endAsleep) {
            sleepEvents.push({ type: "sleep", value: "awake", ts: dayEnd.toISOString(), mock: true });
        }
    }
    
    // Merge consecutive sleep windows (sleep followed by sleep)
    const mergedSleepEvents = [];
    for (let i = 0; i < sleepEvents.length; i++) {
        const event = sleepEvents[i];
        if (event.value === "sleeping" || event.value === "nap") {
            // Check if next event is also a sleep start
            const nextEvent = sleepEvents[i + 1];
            if (nextEvent && (nextEvent.value === "sleeping" || nextEvent.value === "nap")) {
                // Skip this sleep end / next sleep start pair
                continue;
            }
        }
        mergedSleepEvents.push(event);
    }
    sleepEvents = mergedSleepEvents;
    
    // Only count feeds and nappies that occurred within the day
    const feedEvents = activeEntries.filter((e) => {
        return e.type === "feed" && e.value === "bf" && isEntryInDay(e, dayStart, dayEnd);
    });
    
    const wetCount = activeEntries.filter((e) => {
        return e.type === "nappy" && e.value === "wet" && isEntryInDay(e, dayStart, dayEnd);
    }).length;
    
    const dirtyCount = activeEntries.filter((e) => {
        return e.type === "nappy" && e.value === "dirty" && isEntryInDay(e, dayStart, dayEnd);
    }).length;

    let totalSleepMinutes = 0;
    let currentSleepStart = null;

    sleepEvents.forEach((event, i) => {
        if (event.value === "sleeping" || event.value === "nap") {
            currentSleepStart = new Date(event.ts);
        } else if (event.value === "awake" && currentSleepStart) {
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

    return {
        totalSleep: `${hours}h ${minutes}m`,
        feedCount: feedEvents.length,
        wetCount: wetCount,
        dirtyCount: dirtyCount,
    };
}

export function updateStatsDisplay(stats) {
    document.getElementById("stat-sleep").textContent = stats.totalSleep;
    document.getElementById("stat-feeds").textContent = stats.feedCount;
    document.getElementById("stat-wet").textContent = stats.wetCount;
    document.getElementById("stat-dirty").textContent = stats.dirtyCount;
}

export function updateHourlyGrid(entries) {
    const activeEntries = entries.filter(e => !e.deleted);
    for (let hour = 0; hour < 24; hour++) {
        const hourEntries = activeEntries.filter((e) => {
            const entryHour = new Date(e.ts).getHours();
            return entryHour === hour;
        });

        const indicators = ["feed", "sleep", "wet", "dirty"];
        indicators.forEach((type) => {
            const el = document.getElementById(`hour-${hour}-${type}`);
            if (el) {
                const hasEvent = hourEntries.some((e) => {
                    if (type === "feed")
                        return (e.type === "feed" && e.value === "bf");
                    if (type === "sleep")
                        return (e.type === "sleep" && (e.value === "sleeping" || e.value === "nap"));
                    if (type === "wet" || type === "dirty")
                        return (e.type === "nappy" && e.value === type);
                    return e.type === type;
                });
                el.style.opacity = hasEvent ? "1" : "0.2";
            }
        });
    }
}

export function updateSleepAttempts(entries) {
    const activeEntries = entries.filter(e => !e.deleted);
    const sleepEvents = activeEntries.filter((e) => e.type === "sleep");

    const attempts = [];
    let currentAttempt = null;

    sleepEvents.forEach((event, i) => {
        if (event.value === "sleeping" || event.value === "nap") {
            if (currentAttempt) {
                attempts.push(currentAttempt);
            }
            currentAttempt = {
                start: new Date(event.ts),
                type: event.value,
                soothe: [],
            };
        } else if (event.value === "awake" && currentAttempt) {
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

    const container = document.getElementById("sleep-attempts-list");
    container.innerHTML = "";

    attempts.forEach((attempt) => {
        const div = document.createElement("div");
        div.className = `attempt ${attempt.success ? "success" : "fail"}`;

        const timeStr = attempt.start.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
        let durationStr = "";
        if (attempt.end) {
            const mins = Math.round((attempt.end - attempt.start) / 1000 / 60);
            durationStr = `${mins}m`;
        } else {
            durationStr = "ongoing";
        }

        div.innerHTML = `
            <span>${timeStr} - ${attempt.type}</span>
            <span>${durationStr} ${attempt.success ? "✓" : "✗"}</span>
        `;
        container.appendChild(div);
    });
}

export function updateRecentEvents(entries, updateDailyReport, updateButtonStates) {
    const container = document.getElementById("recent-events-list");
    if (!container) return;

    container.innerHTML = "";

    // Show all events for the selected day in reverse chronological order
    const allEvents = [...entries].reverse();

    allEvents.forEach((e) => {
        const div = document.createElement("div");
        div.className = "event-entry";
        
        // Style deleted entries
        if (e.deleted) {
            div.style.opacity = "0.4";
            div.style.textDecoration = "line-through";
            div.style.color = "#999";
        }

        const time = new Date(e.ts);
        const timeStr = time.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });
        
        // Create buttons
        const deleteBtn = document.createElement("button");
        deleteBtn.className = "event-action-btn";
        
        if (e.deleted) {
            deleteBtn.textContent = "↶";
            deleteBtn.style.background = "#4caf50";
            deleteBtn.onclick = () => undeleteEntry(e.key).then(() => { 
                updateDailyReport(); 
                updateButtonStates(); 
            });
        } else {
            deleteBtn.textContent = "🗑";
            deleteBtn.style.background = "#ff6666";
            deleteBtn.onclick = () => markEntryAsDeleted(e.key).then(() => { 
                updateDailyReport(); 
                updateButtonStates(); 
            });
        }

        // Create time span
        const timeSpan = document.createElement("span");
        timeSpan.textContent = timeStr;
        timeSpan.style.cssText = "cursor: pointer; text-decoration: underline;";
        timeSpan.onclick = () => editEntryTime(e.key, e.ts);

        // Create event time container
        const eventTimeContainer = document.createElement("span");
        eventTimeContainer.className = "event-time";
        eventTimeContainer.style.cssText = "display: flex; align-items: center;";
        eventTimeContainer.appendChild(timeSpan);
        eventTimeContainer.appendChild(deleteBtn);

        // Create event content
        const eventContent = document.createElement("div");
        eventContent.innerHTML = `
            <span class="event-type">${e.type}</span><span class="event-value">: ${e.value}</span>
        `;

        div.appendChild(eventContent);
        div.appendChild(eventTimeContainer);
        container.appendChild(div);
    });
}

export function drawTimeline(entries) {
    const container = document.getElementById("timeline-chart");
    container.innerHTML = "";

    const width = container.clientWidth || 600;
    const height = 200;
    const margin = { top: 20, right: 20, bottom: 30, left: 40 };

    const svg = d3
        .select("#timeline-chart")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    // Get day boundaries
    const { dayStart, dayEnd } = getDayBoundsAsDate(currentReportDate);
    
    // Filter out deleted entries
    const activeEntries = entries.filter(e => !e.deleted);
    
    // Get sleep events and add mock events at day boundaries
    let sleepEvents = activeEntries.filter(e => e.type === "sleep");
    
    if (sleepEvents.length === 0) {
        svg.append("text")
            .attr("x", width / 2)
            .attr("y", height / 2)
            .attr("text-anchor", "middle")
            .style("fill", "#999")
            .text("No data for this day");
        return;
    }
    
    // Determine initial state
    const preDaySleepEvents = sleepEvents.filter(e => new Date(e.ts) < dayStart);
    const lastPreDayEvent = preDaySleepEvents.length > 0 ? 
        preDaySleepEvents[preDaySleepEvents.length - 1] : null;
    const startAsleep = lastPreDayEvent && 
        (lastPreDayEvent.value === "sleeping" || lastPreDayEvent.value === "nap");
    
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
    
    // Add mock event at day end
    const inDaySleepEvents = sleepEvents.filter(e => {
        const ts = new Date(e.ts);
        return ts >= dayStart && ts <= dayEnd;
    });
    if (inDaySleepEvents.length > 0) {
        const lastInDayEvent = inDaySleepEvents[inDaySleepEvents.length - 1];
        const endAsleep = lastInDayEvent.value === "sleeping" || lastInDayEvent.value === "nap";
        if (endAsleep) {
            sleepEvents.push({ type: "sleep", value: "awake", ts: dayEnd.toISOString(), mock: true });
        }
    }
    
    // Merge consecutive sleep windows
    const mergedSleepEvents = [];
    for (let i = 0; i < sleepEvents.length; i++) {
        const event = sleepEvents[i];
        if (event.value === "sleeping" || event.value === "nap") {
            const nextEvent = sleepEvents[i + 1];
            if (nextEvent && (nextEvent.value === "sleeping" || nextEvent.value === "nap")) {
                continue;
            }
        }
        mergedSleepEvents.push(event);
    }
    sleepEvents = mergedSleepEvents;
    
    // Convert to line graph data (awake=0, asleep=1)
    const lineData = [];
    sleepEvents.forEach((e) => {
        const date = new Date(e.ts);
        const hours = (date - dayStart) / (1000 * 60 * 60);
        const value = (e.value === "sleeping" || e.value === "nap") ? 1 : 0;
        if (hours >= 0 && hours <= 24) {
            lineData.push({ time: hours, value: value });
        }
    });
    
    // Get feed data for overlay
    const feedData = [];
    activeEntries.forEach((e) => {
        if (e.type === "feed" && e.value === "bf") {
            const date = new Date(e.ts);
            const hours = (date - dayStart) / (1000 * 60 * 60);
            if (hours >= 0 && hours <= 24) {
                feedData.push({ time: hours });
            }
        }
    });

    // Create scales
    const x = d3.scaleLinear().domain([0, 24]).range([margin.left, width - margin.right]);
    const y = d3.scaleLinear().domain([0, 1]).range([height - margin.bottom, margin.top]);

    // Draw gridlines for every hour
    for (let hour = 0; hour <= 24; hour++) {
        svg.append("line")
            .attr("x1", x(hour))
            .attr("x2", x(hour))
            .attr("y1", margin.top)
            .attr("y2", height - margin.bottom)
            .attr("stroke", "#e0e0e0")
            .attr("stroke-width", 1)
            .attr("opacity", 0.5);
    }

    // Draw axes
    svg.append("g")
        .attr("transform", `translate(0,${height - margin.bottom})`)
        .call(
            d3.axisBottom(x)
                .ticks(8)
                .tickValues([0, 3, 6, 9, 12, 15, 18, 21, 24])
                .tickFormat((d) => d + "h")
        );
        
    svg.append("g")
        .attr("transform", `translate(${margin.left},0)`)
        .call(
            d3.axisLeft(y)
                .ticks(2)
                .tickFormat((d) => d === 0 ? "Awake" : "Asleep")
        );

    // Draw line graph using step interpolation
    const line = d3.line()
        .x(d => x(d.time))
        .y(d => y(d.value))
        .curve(d3.curveStepAfter);

    svg.append("path")
        .datum(lineData)
        .attr("fill", "none")
        .attr("stroke", "#2196f3")
        .attr("stroke-width", 3)
        .attr("d", line);
        
    // Add area fill under the line
    const area = d3.area()
        .x(d => x(d.time))
        .y0(y(0))
        .y1(d => y(d.value))
        .curve(d3.curveStepAfter);
        
    svg.append("path")
        .datum(lineData)
        .attr("fill", "#2196f3")
        .attr("opacity", 0.2)
        .attr("d", area);

    // Draw feed events as circles
    feedData.forEach((d) => {
        svg.append("circle")
            .attr("cx", x(d.time))
            .attr("cy", y(0.5))
            .attr("r", 5)
            .attr("fill", "#4caf50");
    });
}