import { html, render } from "https://unpkg.com/htm/preact/index.mjs?module";
import { useState } from "https://unpkg.com/preact@latest/hooks/dist/hooks.module.js?module";

/* bitmask for each cell :
    1<<1 .. 1<<9 : if this bit is set, it means that this value is available in all of row/column/square
    if only one bit is set, the cell is solved
*/
const UNSOLVED = 0x1ff << 1;
// const defaultboard = [...Array(9 * 9)].map(() => UNSOLVED);
const defaultboard = [
  16, 4, 1022, 1022, 64, 256, 128, 2, 1022, 1022, 1022, 1022, 1022, 1022, 128,
  512, 1022, 1022, 1022, 2, 1022, 1022, 1022, 1022, 16, 1022, 32, 256, 1022,
  1022, 1022, 1022, 32, 1022, 1022, 1022, 1022, 32, 1022, 2, 1022, 8, 1022, 128,
  1022, 1022, 1022, 1022, 512, 1022, 1022, 1022, 1022, 16, 1022, 1022, 32, 1022,
  1022, 1022, 1022, 16, 1022, 1022, 1022, 16, 4, 1022, 1022, 1022, 1022, 1022,
  1022, 1022, 64, 256, 512, 1022, 1022, 32, 4,
];
const App = () => {
  const [board, setBoard] = useState(defaultboard);
  const setCell = (cellIndex) => (e) => {
    const newBoard = copy(board);
    const number = parseInt(e.target.value);
    if (number > 0 && number < 10) {
      newBoard[cellIndex] = 1 << number;
    } else {
      newBoard[cellIndex] = UNSOLVED;
    }
    setBoard(newBoard);
  };

  return html`<${Board} ...${{ board, setCell }} />
    <button onClick=${() => setBoard(defaultboard)}>Reset</button>
    <button id="solve" onClick=${() => setBoard(trySolve(board))}>Solve</button>
    <button onClick=${() => setSavedBoard(board)}>Save</button>
    <button onClick=${() => setBoard(getSavedBoard())}>Load</button> `;
};

const Board = ({ board, setCell }) => {
  return html`<div class="board">
    ${board.map(
      (cell, cellIndex) => html`<div class="cell">
        <input
          type="text"
          value=${cellToText(cell)}
          onInput=${setCell(cellIndex)}
        />
      </div>`
    )}
  </div>`;
};

const copy = (board) => [...board];

const cellToText = (cell) => {
  if (cell === UNSOLVED) return "";
  if (solvedCells.has(cell)) return solvedCells.get(cell);
  if (cell === 0) return "X";
  return "?";
};

const trySolve = (board) => {
  const newBoard = copy(board);
  fullSimple(newBoard);
  console.log(`Full simple completed.`);
  const solved = backtrack(newBoard);
  if (solved) {
    return newBoard;
  }
  console.log(`Solve failed.`);
  return board;
};

const log = (depth, cellIndex, value, message) => {
  const cellIndexToRowCol = (cellIndex) => {
    const row = (cellIndex / 9) >> 0;
    const col = cellIndex - row * 9;
    return [row + 1, col + 1];
  };
  console.log(
    `${Array(depth)
      .fill(" ")
      .join("")} ${message} ${value} in cell ${cellIndexToRowCol(cellIndex)}`
  );
};

const backtrack = (board, cellIndex = 0, depth = 0) => {
  log(depth, cellIndex, "", "backtrack");
  if (!boardValid(board)) return null; // invalid, time to backtrack
  if (cellIndex >= 9 * 9) return board; // finished iterating/recursing, complete.
  if (solvedCells.has(board[cellIndex]))
    return backtrack(board, cellIndex + 1, depth + 1); // current cell already solved, continue
  for (let value = 1; value <= 9; value++) {
    if (board[cellIndex] & (1 << value)) {
      log(depth, cellIndex, value, "try");
      const newBoard = copy(board);
      if (!simpleSolve(newBoard, cellIndex, value, depth + 1)) continue;
      let result = backtrack(newBoard, cellIndex + 1, depth + 1);
      if (result) return result;
    }
  }
  return null;
};

const boardValid = (board) => !board.some((cell) => cell === 0);

const solvedCells = new Map([
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

const fullSimple = (board) => {
  for (let cellIndex = 0; cellIndex < 9 * 9; cellIndex++) {
    if (solvedCells.has(board[cellIndex])) {
      const number = solvedCells.get(board[cellIndex]);
      if (!simpleSolve(board, cellIndex, number, 0)) {
        log(0, cellIndex, number, "full simple failed");
      }
    }
  }
};

// eliminate this option from other cells in row/column/square
// return true if board is still valid
const simpleSolve = (board, cellIndex, value, depth) => {
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
    if (!checkRemove(board, cellIndex, boxrow * 9 + boxcol, value, depth + 1))
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
    log(depth, cellIndex, value, "checkRemove solves into ");
    return simpleSolve(board, cellIndex, solvedCells.get(board[cellIndex]), depth + 1);
  }
  if (board[cellIndex] !== previous) {
    log(depth, cellIndex, value, "checkRemove removes ");
  }
  return true;
};

// save the board to local storage
const setSavedBoard = (board) => {
  localStorage.setItem("sudoku", JSON.stringify(board));
};

// retrieve the saved board from local storage
const getSavedBoard = () => {
  const savedBoard = localStorage.getItem("sudoku");
  return savedBoard ? JSON.parse(savedBoard) : defaultboard;
};

console.clear();

render(html`<${App} />`, document.body);
