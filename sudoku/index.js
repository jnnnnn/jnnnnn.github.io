import { h, render } from "https://unpkg.com/preact?module";
import htm from "https://unpkg.com/htm?module";
const html = htm.bind(h);
const App = (props) => html`<h1>Hello ${props.name}!</h1>`;
render(html`<${App} name="World" />`, document.body);
