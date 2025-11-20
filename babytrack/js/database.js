// Database management
let db = null;

// Initialize IndexedDB
export async function initDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open("BabyLogDB", 1);

        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
            db = request.result;
            resolve(db);
        };

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains("entries")) {
                const objectStore = db.createObjectStore(
                    "entries",
                    { autoIncrement: true }
                );
                objectStore.createIndex("timestamp", "ts", {
                    unique: false,
                });
            }
        };
    });
}

// Add a single entry to the database
export async function addEntry(type, value, ts, deleted = false) {
    if (!db) await initDB();

    const transaction = db.transaction(["entries"], "readwrite");
    const objectStore = transaction.objectStore("entries");
    const entry = { type, value, ts, deleted };
    objectStore.add(entry);

    return new Promise((resolve, reject) => {
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
    });
}

// Mark the most recent non-deleted entry as deleted
export async function markMostRecentAsDeleted() {
    if (!db) await initDB();

    const transaction = db.transaction(["entries"], "readwrite");
    const objectStore = transaction.objectStore("entries");
    const index = objectStore.index("timestamp");

    // Get all entries sorted by timestamp descending
    const request = index.openCursor(null, "prev");

    return new Promise((resolve, reject) => {
        request.onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                const entry = cursor.value;
                // Skip already deleted entries
                if (entry.deleted) {
                    cursor.continue();
                    return;
                }
                // Mark as deleted
                entry.deleted = true;
                const key = cursor.key;
                cursor.update(entry);
                resolve({ entry, key });
            } else {
                resolve(null);
            }
        };
        request.onerror = () => reject(request.error);
    });
}

// Undelete an entry by its key
export async function undeleteEntry(key) {
    if (!db) await initDB();

    const transaction = db.transaction(["entries"], "readwrite");
    const objectStore = transaction.objectStore("entries");
    
    return new Promise((resolve, reject) => {
        const request = objectStore.get(key);
        request.onsuccess = () => {
            const entry = request.result;
            if (entry) {
                entry.deleted = false;
                const putRequest = objectStore.put(entry, key);
                putRequest.onsuccess = () => {
                    resolve(entry);
                };
                putRequest.onerror = () => {
                    reject(putRequest.error);
                };
            } else {
                resolve(null);
            }
        };
        request.onerror = () => {
            reject(request.error);
        };
    });
}

// Mark a specific entry as deleted by its key
export async function markEntryAsDeleted(key) {
    if (!db) await initDB();

    const transaction = db.transaction(["entries"], "readwrite");
    const objectStore = transaction.objectStore("entries");
    
    return new Promise((resolve, reject) => {
        const request = objectStore.get(key);
        request.onsuccess = () => {
            const entry = request.result;
            if (entry) {
                entry.deleted = true;
                objectStore.put(entry, key);
                resolve(entry);
            } else {
                resolve(null);
            }
        };
        request.onerror = () => reject(request.error);
    });
}

// Update an entry's timestamp
export async function updateEntryTimestamp(key, newTimestamp) {
    if (!db) await initDB();

    const transaction = db.transaction(["entries"], "readwrite");
    const objectStore = transaction.objectStore("entries");
    
    return new Promise((resolve, reject) => {
        const request = objectStore.get(key);
        request.onsuccess = () => {
            const entry = request.result;
            if (entry) {
                entry.ts = newTimestamp;
                objectStore.put(entry, key);
                resolve(entry);
            } else {
                resolve(null);
            }
        };
        request.onerror = () => reject(request.error);
    });
}

export async function loadEntriesByDate(date) {
    if (!db) await initDB();

    const transaction = db.transaction(["entries"], "readonly");
    const objectStore = transaction.objectStore("entries");
    
    let range;
    if (date) {
        const { start, end } = getDayBounds(date);
        // Query 12 hours before and after to catch sleep periods that cross midnight
        const expandedStart = new Date(new Date(start).getTime() - 12 * 60 * 60 * 1000).toISOString();
        const expandedEnd = new Date(new Date(end).getTime() + 12 * 60 * 60 * 1000).toISOString();
        range = IDBKeyRange.bound(expandedStart, expandedEnd);
    } else {
        const yesterday = new Date(Date.now() - 36 * 60 * 60 * 1000).toISOString();
        range = IDBKeyRange.lowerBound(yesterday);
    }
    
    const index = objectStore.index("timestamp");
    const request = index.openCursor(range);
    const results = [];

    return new Promise((resolve, reject) => {
        request.onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                const entry = cursor.value;
                entry.key = cursor.key; // Store the key with the entry
                results.push(entry);
                cursor.continue();
            } else {
                resolve(results);
            }
        };
        request.onerror = () => reject(request.error);
    });
}

export async function loadTodayEntries() {
    if (!db) await initDB();

    const today = new Date();
    const { start, end } = getDayBounds(today);
    const transaction = db.transaction(["entries"], "readonly");
    const objectStore = transaction.objectStore("entries");
    
    return new Promise((resolve, reject) => {
        const results = [];
        const index = objectStore.index("timestamp");
        const request = index.openCursor(IDBKeyRange.bound(start, end));
        
        request.onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                const entry = cursor.value;
                entry.key = cursor.primaryKey; // Add the IndexedDB key to the entry
                results.push(entry);
                cursor.continue();
            } else {
                resolve(results);
            }
        };
        request.onerror = () => reject(request.error);
    });
}

export async function clearAllEntries() {
    if (!db) await initDB();

    const transaction = db.transaction(["entries"], "readwrite");
    const objectStore = transaction.objectStore("entries");
    objectStore.clear();

    return new Promise((resolve, reject) => {
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
    });
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