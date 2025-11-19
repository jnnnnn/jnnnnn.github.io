import { markEntryAsDeleted, undeleteEntry } from './database.js';
import { editEntryTime } from './ui.js';
import { 
    getDayBoundsAsDate, 
    isEntryInDay, 
    filterEntriesInDay, 
    processSleepEventsForDay, 
    mergeConsecutiveSleepEvents, 
    calculateSleepDuration, 
    convertSleepEventsToTimelineData, 
    processSleepAttempts 
} from './time.js';

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
    
    // Process sleep events using the time module
    let sleepEvents = processSleepEventsForDay(entries, dayStart, dayEnd);
    sleepEvents = mergeConsecutiveSleepEvents(sleepEvents);
    
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

    // Calculate sleep duration using the time module
    const { hours, minutes } = calculateSleepDuration(sleepEvents, dayStart, dayEnd, currentReportDate);

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
    const attempts = processSleepAttempts(entries);

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
    
    // Get sleep events and process them
    let sleepEvents = processSleepEventsForDay(entries, dayStart, dayEnd);
    
    if (sleepEvents.filter(e => !e.mock).length === 0) {
        svg.append("text")
            .attr("x", width / 2)
            .attr("y", height / 2)
            .attr("text-anchor", "middle")
            .style("fill", "#999")
            .text("No data for this day");
        return;
    }
    
    // Merge consecutive sleep events and convert to timeline data
    sleepEvents = mergeConsecutiveSleepEvents(sleepEvents);
    const lineData = convertSleepEventsToTimelineData(sleepEvents, dayStart);
    
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