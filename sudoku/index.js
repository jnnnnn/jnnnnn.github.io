import { html, render } from "https://unpkg.com/htm/preact/index.mjs?module";
import { useState } from "https://unpkg.com/preact@latest/hooks/dist/hooks.module.js?module";

const defaultboard = [...Array(9)].map(() => [...Array(9)].map(() => 1 << 11));
const App = (props) => {
  const [board, setBoard] = useState(defaultboard);
  const setCell = (row, col) => (e) => {
    const newBoard = [...board];
    newBoard[row][col] = e.target.value;
    setBoard(newBoard);
    console.log(newBoard);
  };

  return html`<${Board} ...${{ board, setCell }} />`;
};

const Board = ({ board, setCell }) => {
  return html`<table>
    ${board.map(
      (row, rowindex) => html`<tr>
        ${row.map(
          (cell, colindex) => html`<td>
            <input
              type="text"
              value=${cell}
              onInput=${setCell(rowindex, colindex)}
            />
          </td>`
        )}
      </tr>`
    )}
  </table>`;
};

render(html`<${App} />`, document.body);
