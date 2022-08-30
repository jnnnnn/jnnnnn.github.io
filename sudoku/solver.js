export const trySolve = (board) => {
    console.clear();
    const newBoard = copy(board);
    if (!simpleSolveGrid(newBoard)) {
        console.log("simple solve failed");
        return board;
    }
    const solved = backtrack(newBoard);
    if (solved) return solved;
    console.log(`Solve failed.`);
    return board;
};

export const copy = (board) => [...board];

const log = (depth, cellIndex, value, message) => {
    const cellIndexToRowCol = (cellIndex) => {
        const row = (cellIndex / 9) >> 0;
        const col = cellIndex - row * 9;
        return [row + 1, col + 1];
    };
    console.log(
        `${Array(depth)
            .fill(" ")
            .join("")} ${message} ${value} in cell ${cellIndexToRowCol(
            cellIndex
        )}`
    );
};

// try whatever possibilities are still available in the first cell we find
const backtrack = (board, cellIndex = 0, depth = 0) => {
    if (cellIndex >= 9 * 9) return board; // finished iterating/recursing, complete.
    log(depth, cellIndex, "", "backtrack");
    if (solvedCells.has(board[cellIndex]))
        return backtrack(board, cellIndex + 1, depth + 1); // current cell already solved, continue
    for (let value = 1; value <= 9; value++) {
        if (board[cellIndex] & (1 << value)) {
            log(depth, cellIndex, value, "try");
            const newBoard = copy(board);
            if (!simpleSolveCell(newBoard, cellIndex, value, depth + 1))
                continue;
            let result = backtrack(newBoard, cellIndex + 1, depth + 1);
            if (result) return result;
        }
    }
    return null;
};

export const solvedCells = new Map([
    [1 << 1, 1],
    [1 << 2, 2],
    [1 << 3, 3],
    [1 << 4, 4],
    [1 << 5, 5],
    [1 << 6, 6],
    [1 << 7, 7],
    [1 << 8, 8],
    [1 << 9, 9],
]);

const simpleSolveGrid = (board) => {
    for (let cellIndex = 0; cellIndex < 9 * 9; cellIndex++) {
        if (solvedCells.has(board[cellIndex])) {
            const number = solvedCells.get(board[cellIndex]);
            if (!simpleSolveCell(board, cellIndex, number, 0)) {
                log(0, cellIndex, number, "full simple failed");
            }
        }
    }
};

// eliminate this possibility from other cells in row/column/square
// return true if board is still valid
const simpleSolveCell = (board, cellIndex, value, depth) => {
    log(depth, cellIndex, value, "simpleSolve");
    const row = (cellIndex / 9) >> 0;
    const col = cellIndex - row * 9;
    for (let i = 0; i < 9; i++) {
        const boxrow = ((row / 3) >> 0) * 3 + ((i / 3) >> 0);
        const boxcol = ((col / 3) >> 0) * 3 + (i % 3);
        if (!checkRemove(board, cellIndex, row * 9 + i, value, depth + 1))
            return false;
        if (!checkRemove(board, cellIndex, i * 9 + col, value, depth + 1))
            return false;
        if (
            !checkRemove(
                board,
                cellIndex,
                boxrow * 9 + boxcol,
                value,
                depth + 1
            )
        )
            return false;
    }
    board[row * 9 + col] = 1 << value;
    log(depth, cellIndex, value, "simple solve completed");
    return true;
};

// Remove the given possibility from the given cell.
// If this solves the cell, propagate the solved cell to other cells in the same row/column/square
const checkRemove = (board, causingcellIndex, cellIndex, value, depth) => {
    if (causingcellIndex == cellIndex) return true;
    //log(depth, cellIndex, value, "checkRemove tests");
    const already = solvedCells.has(board[cellIndex]);
    const previous = board[cellIndex];
    board[cellIndex] &= ~(1 << value);
    if (board[cellIndex] === 0) {
        log(depth, cellIndex, value, "checkRemove reject");
        return false;
    }
    if (!already && solvedCells.has(board[cellIndex])) {
        const number = solvedCells.get(board[cellIndex]);
        log(depth, cellIndex, number, "checkRemove solved");
        return simpleSolveCell(board, cellIndex, number, depth + 1);
    }
    if (board[cellIndex] !== previous) {
        log(depth, cellIndex, value, "checkRemove removes ");
    }
    return true;
};
