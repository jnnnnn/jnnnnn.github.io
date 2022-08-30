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
    const [selectedNumber, setSelectNumber] = useState(0);
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
        <${Board} ...${{ board, setBoard, setCell, selectedNumber }} />
        <div class="buttons">
            ${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map(
                (number) =>
                    html`<${NumberButton} ...${{ number, setSelectNumber }} />`
            )}
        </div>
        <button onClick=${() => setBoard(defaultboard)}>Reset</button>
        <button id="solve" onClick=${() => setBoard(trySolve(board))}>
            Solve
        </button>
        <button onClick=${() => setSavedBoard(board)}>Save</button>
        <button onClick=${() => setBoard(getSavedBoard())}>Load</button>
    </div>`;
};

const Cell =
    ({ board, setBoard, setCell, selectedNumber }) =>
    (cell, cellIndex) =>
        html`<div class="cell">
            <input
                type="text"
                value=${cellToText(cell)}
                onInput=${setCell(cellIndex)}
                onMouseDown=${CellClick({
                    board,
                    setBoard,
                    cellIndex,
                    selectedNumber,
                })}
            />
        </div>`;

const CellClick =
    ({ board, setBoard, cellIndex, selectedNumber }) =>
    (e) => {
        e.preventDefault();
        const newBoard = copy(board);
        newBoard[cellIndex] = selectedNumber ? 1 << selectedNumber : UNSOLVED;
        setBoard(newBoard);
    };

const Board = ({ board, setBoard, setCell, selectedNumber }) => {
    return html`<div class="board">
        ${board.map(Cell({ board, setBoard, setCell, selectedNumber }))}
    </div>`;
};

// When this button is pressed, it sets the selected number
const NumberButton = ({ number, setSelectNumber }) =>
    html`<button onClick=${() => setSelectNumber(number)}>${number}</button>`;

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
