# Book Graph app

I have been drawing (on paper) graphical summaries of books for a while now, to help me remember the parts I found interesting or useful. This proves very helpful later when discussing the book with other people.

One of the problems with drawing graphs on paper is that once something is drawn, it can't be moved.

I want some software that will let me draw graphs very quickly, creating nodes and linking them together and moving them around.

I've done a few little projects in d3 already (see [here](jnnnnn.github.io)) so I will try to do a canvas thing.

The following are notes that I took during the devlopment process.

## 2020-01-18

Started! Base a simple chart on https://bl.ocks.org/jodyphelan/5dc989637045a0f48418101423378fbd . Unfortunately this doesn't work with d3 v5, I'm going to have to start again. Drat.

OK, let's just get a canvas on the page. I don't want to use SVG because the performance gets bad and working out what was clicked on gets tricky.

Oh, if I have a script in the body it has to go after any of the elements it references, otherwise the browser won't find them in the DOM.

Investigating whether I can do it in 3d? Maybe... https://bl.ocks.org/vasturiano/f59675656258d3f490e9faa40828c0e7 is pretty cool. Exploring that network of bl.ocks shows some interesting bl.ocks that are linked to several others.

Starting to make sure everything stays manageable. No unit tests yet, but global state is explicit now and I have started moving related functions (the drag handlers) into separate files.

## 2020-02-01

Working on stuff. Mouse following. Key press. Worked out the difference between screen space and model space. Screen space changes when we zoom or pan, but model space doesn't. Forces are calculated in model space. The nodes have values in model space. Rendering is done in model space but with the zoom/pan transform applied to the canvas graphics context.

Implemented selection. Currently selected node is stored in model and drawn differently.

Implemented link and unlink commands. Unlink not working properly.

## 2020-02-02

Got a little confused, thought state.edges was a list of pairs of ids, but it's actually pairs of (pointers to) real nodes.

Next step is an "edit" command to change text, then a "new node" command will be easy, and deleting nodes, then resizing nodes (with `+` and `-` or maybe shift+zoom?)

The edit command is a little tricky because the edit box has to appear and disappear. `state` could have an "editingNode" value? Yeah, seems reasonable.

Work out proper state mutation foundation first, so that we have an undo stack.

Change scaling to be truly quadratic so that zoom down to very small levels still works.

Got the edit box appearing. CSS is cool and good. Replacing a node is tricky, there are lots of links to it everywhere:

- edge .source and .target
- simulation

I tried to fix these places but it's still going blank after updating a node. I think it might be time to use a better state management pattern; updating everything that needs it is starting to become so error-prone that it's slowing me down.

Unfortunately, using react means using a javascript compiler. I don't want to do that. The preact docs talk about alternatives to transpiling. https://preactjs.com/guide/v10/getting-started#no-build-tools-route . Basically tagged templates. It looks good but I don't know how long editor support for it will last. https://github.com/developit/htm

I will keep this in mind for a rewrite but I'm going to just try and fix my bug for now.

Printing out the complete state before and after the mutation shows that the only thing that changed is the node's text. Everything else was copied correctly. Perhaps something was copied that shouldn't have been?

Ah, just trying to mutate the existing node also doesn't work. So there is some other problem.

Oh shit.

```js
document.body.remove(textarea);
```

This actually removes the body. lol.

Finished the undo implementation by restoring state off the stack. Works first try.

Improving editing behaviour: ctrl+enter saves, escape cancels.

Noticed my first bug: the selected node doesn't get updated when we replace a node by editing it.

Last things to do are:

- new node (done)
- delete node (done)
- resize node (super easy)
- persist state
- Should new node be "n" or "e" over an empty space? try "e" to start with (done)
- Clicking a node should select it.
- A new node should be linked to the selected one if an existing node was selected. New nodes should be one size smaller than their parent by default.
- Creating a new node not linked to anything should also select it.

Clicking nodes is a little tricky because the click happens in index.js. I initially started calling into the select command directly but it would be better to have the click handler itself in index.js.

Also, almost every mutation of state requires the simulation to be restarted so do that.

Clicking works.

Things to do:

- I think the last thing left to do is persist state.
- Oh, and make the lines not draw all the way to the nodes.
- And make newlines work so nodes can have several rows
- and maybe get rid of the circles
- and center the text vertically on the nodes

Saving a file works. I should be persisting state in localStorage. Not sure how often to do that though.
