// Test data generation function
export async function generateTestData(addEntry) {
    const days = 7; // Generate a week of data
    const now = new Date();

    for (let day = days - 1; day >= 0; day--) {
        const baseDate = new Date(now);
        baseDate.setDate(baseDate.getDate() - day);
        baseDate.setHours(0, 0, 0, 0);

        // Generate sleep patterns (roughly 3-4 sleep cycles per day)
        const sleepCycles = 3 + Math.floor(Math.random() * 2);

        for (let cycle = 0; cycle < sleepCycles; cycle++) {
            // Sleep start time (spread throughout 24 hours)
            const sleepHour = Math.floor(
                (24 / sleepCycles) * cycle + Math.random() * 2
            );
            const sleepMinute = Math.floor(Math.random() * 60);

            const sleepStart = new Date(baseDate);
            sleepStart.setHours(sleepHour, sleepMinute);

            // Sleep type: longer sleep at night, naps during day
            const sleepType =
                sleepHour >= 20 || sleepHour < 6
                    ? "sleeping"
                    : "nap";
            await addEntry(
                "sleep",
                sleepType,
                sleepStart.toISOString()
            );

            // Sleep duration: 30min to 3 hours for naps, 2-5 hours for night sleep
            let durationMinutes;
            if (sleepType === "nap") {
                durationMinutes = 30 + Math.random() * 150;
            } else {
                durationMinutes = 120 + Math.random() * 180;
            }

            const awakeTime = new Date(sleepStart);
            awakeTime.setMinutes(
                awakeTime.getMinutes() + durationMinutes
            );

            // Sometimes add soothe methods before sleep
            if (Math.random() > 0.5) {
                const sootheBefore = new Date(sleepStart);
                sootheBefore.setMinutes(
                    sootheBefore.getMinutes() - 5
                );
                const sootheMethod = [
                    "rocking",
                    "pram",
                    "wearing",
                    "feed-to-sleep",
                ][Math.floor(Math.random() * 4)];
                await addEntry(
                    "soothe",
                    sootheMethod,
                    sootheBefore.toISOString()
                );
            }

            await addEntry(
                "sleep",
                "awake",
                awakeTime.toISOString()
            );
        }

        // Generate feeding events (every 2-4 hours, ~6-8 feeds per day)
        const feedCount = 6 + Math.floor(Math.random() * 3);

        for (let feed = 0; feed < feedCount; feed++) {
            const feedHour = Math.floor(
                (24 / feedCount) * feed + Math.random() * 2
            );
            const feedMinute = Math.floor(Math.random() * 60);

            const feedTime = new Date(baseDate);
            feedTime.setHours(feedHour, feedMinute);

            await addEntry(
                "feed",
                "bf",
                feedTime.toISOString()
            );

            // Sometimes spew after feeding
            if (Math.random() > 0.7) {
                const spewTime = new Date(feedTime);
                spewTime.setMinutes(
                    spewTime.getMinutes() +
                        10 +
                        Math.random() * 30
                );
                await addEntry(
                    "feed",
                    "spew",
                    spewTime.toISOString()
                );
            }

            // Occasional grizzle
            if (Math.random() > 0.8) {
                const grizzleTime = new Date(feedTime);
                grizzleTime.setMinutes(
                    grizzleTime.getMinutes() -
                        5 -
                        Math.random() * 10
                );
                await addEntry(
                    "feed",
                    "grizzle",
                    grizzleTime.toISOString()
                );
            }
        }

        // Generate Nappy changes (roughly 6-10 per day)
        const NappyCount = 6 + Math.floor(Math.random() * 5);

        for (let Nappy = 0; Nappy < NappyCount; Nappy++) {
            const NappyHour = Math.floor(
                (24 / NappyCount) * Nappy + Math.random() * 2
            );
            const NappyMinute = Math.floor(Math.random() * 60);

            const NappyTime = new Date(baseDate);
            NappyTime.setHours(NappyHour, NappyMinute);

            // Most Nappies are wet
            await addEntry(
                "nappy",
                "wet",
                NappyTime.toISOString()
            );

            // About half are also dirty
            if (Math.random() > 0.5) {
                await addEntry(
                    "nappy",
                    "dirty",
                    NappyTime.toISOString()
                );
            }
        }

        // Occasional use of 5 S's techniques
        const fiveSCount = Math.floor(Math.random() * 4);
        for (let i = 0; i < fiveSCount; i++) {
            const fiveSHour = Math.floor(Math.random() * 24);
            const fiveSMinute = Math.floor(Math.random() * 60);

            const fiveSTime = new Date(baseDate);
            fiveSTime.setHours(fiveSHour, fiveSMinute);

            const technique = [
                "swaddle",
                "side-lying",
                "shush",
                "swing",
                "suck",
            ][Math.floor(Math.random() * 5)];
            await addEntry(
                "5s",
                technique,
                fiveSTime.toISOString()
            );
        }

        // Add occasional notes
        if (Math.random() > 0.6) {
            const noteHour = Math.floor(Math.random() * 24);
            const noteMinute = Math.floor(Math.random() * 60);

            const noteTime = new Date(baseDate);
            noteTime.setHours(noteHour, noteMinute);

            const notes = [
                "Good day!",
                "A bit fussy today",
                "Slept well",
                "Cluster feeding",
                "Very alert and happy",
                "Seems gassy",
                "Long stretch of sleep!",
                "Growth spurts?",
            ];
            await addEntry(
                "note",
                notes[Math.floor(Math.random() * notes.length)],
                noteTime.toISOString()
            );
        }
    }

    console.log(`Generated ${days} days of test data`);
}