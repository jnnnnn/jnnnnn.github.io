import { html, render } from "https://unpkg.com/htm/preact/index.mjs?module";
import { useState } from "https://unpkg.com/preact@latest/hooks/dist/hooks.module.js?module";
import { trySolve, solvedCells, copy } from "./solver.js";
/* bitmask for each cell :
    1<<1 .. 1<<9 : if this bit is set, it means that this value is available in all of row/column/square
    if only one bit is set, the cell is solved
*/
const UNSOLVED = 0x1ff << 1;
const defaultboard = [...Array(9 * 9)].map(() => UNSOLVED);
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

  return html`<div class="app">
    <${Board} ...${{ board, setCell }} />
    <button onClick=${() => setBoard(defaultboard)}>Reset</button>
    <button id="solve" onClick=${() => setBoard(trySolve(board))}>Solve</button>
    <button onClick=${() => setSavedBoard(board)}>Save</button>
    <button onClick=${() => setBoard(getSavedBoard())}>Load</button>
  </div>`;
};

const Board = ({ board, setCell }) => {
  return html`<div class="board">
    ${board.map(
      (cell, cellIndex) => html`<div class="cell">
        <input
          type="number"
          value=${cellToText(cell)}
          onInput=${setCell(cellIndex)}
        />
      </div>`
    )}
  </div>`;
};

const cellToText = (cell) => {
  if (cell === UNSOLVED) return "";
  if (solvedCells.has(cell)) return solvedCells.get(cell);
  if (cell === 0) return "X";
  return "?";
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

render(html`<${App} />`, document.body);
