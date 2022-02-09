import { html, render } from "https://unpkg.com/htm/preact/index.mjs?module";
import { useState } from "https://unpkg.com/preact@latest/hooks/dist/hooks.module.js?module";

/* bitmask for each cell :
    1<<1 .. 1<<9 : if this bit is set, it means that this value is available in all of row/column/square
    if only one bit is set, the cell is solved
*/
const UNSOLVED = 0x1ff << 1;
const defaultboard = [...Array(9 * 9)].map(() => UNSOLVED);
const App = () => {
  const [board, setBoard] = useState(defaultboard);
  const [savedBoard, setSavedBoard] = useState(defaultboard);
  const setCell = (cellIndex) => (e) => {
    const newBoard = copy(board);
    const number = parseInt(e.target.value);
    if (number > 0 && number < 10) {
      simpleSolve(newBoard, cellIndex, number);
    } else {
      newBoard[cellIndex] = UNSOLVED;
    }
    setBoard(newBoard);
  };

  return html`<${Board} ...${{ board, setCell }} />
    <button onClick=${() => setBoard(defaultboard)}>Reset</button>
    <button id="solve" onClick=${() => setBoard(backtrack(board, 0))}>
      Solve
    </button>
    <button onClick=${() => setSavedBoard(board)}>Save</button>
    <button onClick=${() => setBoard(savedBoard)}>Load</button> `;
};

const Board = ({ board, setCell }) => {
  return html`<div class="board">
    ${board.map(
      (cell, cellIndex) => html`<div class="cell">
        <input
          type="text"
          value=${solvedCells.has(cell) ? solvedCells.get(cell) : ""}
          onInput=${setCell(cellIndex)}
        />
      </div>`
    )}
  </div>`;
};

const copy = (board) => [...board];
const backtrack = (board, cellIndex) => {
  if (board.some((cell) => cell === 0)) return null; // invalid, time to backtrack
  if (cellIndex >= 9 * 9) return board; // finished iterating/recursing, complete.
  if (solvedCells.has(board[cellIndex])) return backtrack(board, cellIndex + 1); // current cell already solved, continue
  for (let value = 1; value <= 9; value++) {
    if (board[cellIndex] & (1 << value)) {
      const newBoard = copy(board);
      if (!simpleSolve(newBoard, cellIndex, value)) continue;
      let result = backtrack(newBoard, cellIndex + 1);
      if (result) return result;
    }
  }
  return null;
};

const solvedCells = new Map(
  [...new Array(9)].map((_, i) => [1 << (i + 1), i + 1])
);

// eliminate this option from other cells in row/column/square
// return true if board is still valid
const simpleSolve = (board, cellindex, value) => {
  const row = (cellindex / 9) >> 0;
  const col = cellindex - row * 9;
  for (let i = 0; i < 9; i++) {
    const boxrow = ((row / 3) >> 0) * 3 + ((i / 3) >> 0);
    const boxcol = ((col / 3) >> 0) * 3 + (i % 3);
    if (!checkRemove(board, row * 9 + i, value)) return false;
    if (!checkRemove(board, i * 9 + col, value)) return false;
    if (!checkRemove(board, boxrow * 9 + boxcol, value)) return false;
  }
  board[row * 9 + col] = 1 << value;
  return true;
};

// Remove the given possibility from the given cell. 
// If this solves the cell, propagate the solved cell to other cells in the same row/column/square
const checkRemove = (board, cellIndex, value) => {
  const already = solvedCells.has(board[cellIndex]);
  board[cellIndex] &= ~(1 << value);
  if (board[cellIndex] === 0) return false;
  if (!already && solvedCells.has(board[cellIndex]))
    return simpleSolve(board, cellIndex, value);
  return true;
};

render(html`<${App} />`, document.body);

setTimeout(() => document.getElementById("solve").click(), 1000);
