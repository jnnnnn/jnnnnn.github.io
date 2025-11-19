// Helper to find last sleep start entry
export function findLastSleepStart(entries) {
    return [...entries]
        .reverse()
        .find(e => e.type === "sleep" && (e.value === "sleeping" || e.value === "nap"));
}