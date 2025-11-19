import { nowIso, formatElapsedTime } from './database.js';

// Button Configuration
const buttonGroups = [
    {
        buttons: [
            { type: "feed", value: "bf", label: "Feed" },
            { type: "feed", value: "play", label: "Play" },
        ],
    },
    {
        buttons: [
            { type: "sleep", value: "sleeping", label: "Sleeping" },
            { type: "sleep", value: "nap", label: "Nap" },
            { type: "sleep", value: "awake", label: "Awake" },
            { type: "sleep", value: "grizzle", label: "Grizzle" },
        ],
    },
    {
        buttons: [
            { type: "nappy", value: "wet", label: "Wet" },
            { type: "nappy", value: "dirty", label: "Dirty" },
            { type: "nappy", value: "spew", label: "Spew" },
        ],
    },
    {
        buttons: [
            { type: "soothe", value: "pram", label: "Pram" },
            { type: "soothe", value: "rocking", label: "Rocking" },
            { type: "soothe", value: "wearing", label: "Wearing" },
            {
                type: "soothe",
                value: "feed-to-sleep",
                label: "Feed to Sleep",
            },
        ],
    },
    {
        buttons: [
            { type: "5s", value: "swaddle", label: "Swaddle" },
            {
                type: "5s",
                value: "side-lying",
                label: "Side/Stomach",
            },
            { type: "5s", value: "shush", label: "Shush" },
            { type: "5s", value: "swing", label: "Swing" },
            { type: "5s", value: "suck", label: "Suck" },
        ],
    },
];

// Long-press detection
let longPressTimer = null;
let longPressData = null;

export function handleLongPressStart(type, value, btn, event) {
    event.preventDefault();
    longPressTimer = setTimeout(() => {
        // Show time picker modal
        longPressData = { type, value, btn };
        showTimePicker();
    }, 500); // 500ms for long press
}

export function handleLongPressEnd() {
    if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }
}

export function showTimePicker() {
    const modal = document.getElementById("time-picker-modal");
    const input = document.getElementById("custom-time");

    // Set default to current time in local timezone
    // datetime-local expects format: YYYY-MM-DDTHH:mm
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    input.value = `${year}-${month}-${day}T${hours}:${minutes}`;

    modal.classList.add("show");
}

export function hideTimePicker() {
    const modal = document.getElementById("time-picker-modal");
    modal.classList.remove("show");
    longPressData = null;
}

export function getLongPressData() {
    return longPressData;
}

// Generate buttons dynamically
export function renderButtons() {
    const container = document.querySelector(".container");
    const h2 = container.querySelector("h2");

    // Remove existing button cards
    const existingCards = container.querySelectorAll(
        ".card:not(#daily-report .card)"
    );
    existingCards.forEach((card) => {
        if (!card.querySelector("#notes")) {
            card.remove();
        }
    });

    // Insert button groups after the h2
    buttonGroups.reverse().forEach((group) => {
        const card = document.createElement("div");
        card.className = "card";

        const row = document.createElement("div");
        row.className = "row";

        group.buttons.forEach((btn) => {
            const button = document.createElement("button");
            button.className = "action";
            button.dataset.type = btn.type;
            button.dataset.value = btn.value;
            button.textContent = btn.label;
            button.onclick = function () {
                // Import save function when needed
                import('./app.js').then(({ save }) => {
                    save(btn.type, btn.value, this);
                });
            };
            button.onpointerdown = function (e) {
                handleLongPressStart(btn.type, btn.value, this, e);
            };
            button.onpointerup = handleLongPressEnd;
            button.onpointercancel = handleLongPressEnd;

            row.appendChild(button);
        });

        card.appendChild(row);
        h2.insertAdjacentElement("afterend", card);
    });
}

// Helper to update button display with time and highlight
export function updateButtonDisplay(btn, label, timeStr = null, highlight = false) {
    if (!btn) return;
    const opacity = highlight ? "0.9" : "0.8";
    btn.style.background = highlight ? "var(--primary)" : "";
    btn.style.color = highlight ? "#fff" : "";
    btn.innerHTML = timeStr 
        ? `${label}<br><small style="font-size: 11px; opacity: ${opacity};">${timeStr}</small>`
        : label;
}

export async function updateButtonStates(loadTodayEntries) {
    const allEntries = await loadTodayEntries();

    if (!allEntries || allEntries.length === 0) return;

    // Filter out deleted entries
    const activeEntries = allEntries.filter(e => !e.deleted);

    // Find last feed and update button
    const lastFeed = [...activeEntries].reverse().find(e => e.type === "feed" && e.value === "bf");
    const feedBtn = document.querySelector('button[data-type="feed"][data-value="bf"]');
    const feedTime = lastFeed ? formatElapsedTime(new Date(lastFeed.ts).getTime()) : null;
    updateButtonDisplay(feedBtn, "Feed", feedTime, false);

    // Find last sleep event and update sleep/awake buttons
    const lastSleepEvent = [...activeEntries].reverse().find(e => e.type === "sleep");
    const sleepBtn = document.querySelector('button[data-type="sleep"][data-value="sleeping"]');
    const awakeBtn = document.querySelector('button[data-type="sleep"][data-value="awake"]');

    if (sleepBtn && awakeBtn) {
        const isAsleep = lastSleepEvent && (lastSleepEvent.value === "sleeping" || lastSleepEvent.value === "nap");
        const sleepTime = lastSleepEvent ? formatElapsedTime(new Date(lastSleepEvent.ts).getTime()) : null;
        
        if (lastSleepEvent) {
            updateButtonDisplay(sleepBtn, "Sleeping", isAsleep ? sleepTime : null, isAsleep);
            updateButtonDisplay(awakeBtn, "Awake", !isAsleep ? sleepTime : null, !isAsleep);
        } else {
            // No sleep events today - default to awake
            updateButtonDisplay(sleepBtn, "Sleeping", null, false);
            updateButtonDisplay(awakeBtn, "Awake", null, true);
        }
    }
}

export function updateTimestamp(text) {
    const stamp = document.getElementById("laststamp");
    if (stamp) stamp.textContent = text;
}

export function editEntryTime(key, currentTs) {
    // Show modal with current time pre-filled
    const modal = document.getElementById("time-picker-modal");
    const input = document.getElementById("custom-time");

    const current = new Date(currentTs);
    const year = current.getFullYear();
    const month = String(current.getMonth() + 1).padStart(2, '0');
    const day = String(current.getDate()).padStart(2, '0');
    const hours = String(current.getHours()).padStart(2, '0');
    const minutes = String(current.getMinutes()).padStart(2, '0');
    input.value = `${year}-${month}-${day}T${hours}:${minutes}`;

    modal.classList.add("show");

    // Store the key for updating
    window.editingEntryKey = key;
}