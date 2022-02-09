import { html, render } from "https://unpkg.com/htm/preact/index.mjs?module";
import { useState } from "https://unpkg.com/preact@latest/hooks/dist/hooks.module.js?module";

const flag = 1 << 11;

const defaultboard = [...Array(9)].map(() => [...Array(9)].map(() => flag));
const App = (props) => {
  const [board, setBoard] = useState(defaultboard);
  const setCell = (row, col) => (e) => {
    const newBoard = copy(board);
    const number = parseInt(e.target.value);
    newBoard[row][col] = number > 0 && number < 10 ? number : flag;
    setBoard(newBoard);
    console.log(newBoard);
  };

  return html`<${Board} ...${{ board, setCell }} />
    <button onClick=${() => setBoard(defaultboard)}>Reset</button>
    <button onClick=${() => setBoard(solve(board))}>Solve</button> `;
};

const Board = ({ board, setCell }) => {
  return html`<div class="board">
    ${board.map((row, rowindex) =>
      row.map(
        (cell, colindex) => html`<div class="cell">
          <input
            type="text"
            value=${cell < 10 ? cell : ""}
            onInput=${setCell(rowindex, colindex)}
          />
        </div>`
      )
    )}
  </div>`;
};

const copy = (board) => board.map((row) => [...row]);

render(html`<${App} />`, document.body);
