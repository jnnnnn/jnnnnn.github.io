// CSV Export functionality
export async function downloadCSV(loadEntriesByDate) {
    const entries = await loadEntriesByDate();

    if (!entries || entries.length === 0) {
        alert("No data to export");
        return;
    }

    const header = "Timestamp,Type,Value";
    const rows = entries.map((e) => {
        // Convert UTC timestamp to ISO format with local timezone offset
        const date = new Date(e.ts);
        const offset = -date.getTimezoneOffset();
        const sign = offset >= 0 ? '+' : '-';
        const hours = String(Math.floor(Math.abs(offset) / 60)).padStart(2, '0');
        const mins = String(Math.abs(offset) % 60).padStart(2, '0');
        
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hour = String(date.getHours()).padStart(2, '0');
        const minute = String(date.getMinutes()).padStart(2, '0');
        const second = String(date.getSeconds()).padStart(2, '0');
        
        const localTime = `${year}-${month}-${day}T${hour}:${minute}:${second}${sign}${hours}:${mins}`;
        return `"${localTime}","${e.type}","${e.value}"`;
    });
    const csv = [header, ...rows].join("\n");

    const blob = new Blob([csv], {
        type: "text/csv;charset=utf-8;",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download =
        "baby_log_" +
        new Date().toISOString().split("T")[0] +
        ".csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}