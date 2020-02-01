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
