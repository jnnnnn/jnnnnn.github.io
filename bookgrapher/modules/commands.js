import { findNodeAtCoords } from "./model.js";

export const keydown = state => key => {
  switch (key) {
    case "s":
      select(state);
      break;
  }
};

const select = state => {
  state.selected = findNodeAtCoords(state)(state.mouse);
};
