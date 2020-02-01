# procal: A simple Qt-based programming calculator


![Demo](img/procal_demo.gif)

The input text is `eval()`'d as python code. If the result can be cast to `int` and fits within 32 bits, the bit fields are updated.

## why?
I wrote this after some frustration with the default Gnome calculator's programming mode:
1. Not each bit is labeled, and I'd rather not count bits if I can avoid it.
2. You cannot click-and-drag to toggle multiple bits in gnome-calc.
3. gnome-calc does not understand hex strings starting with `0x`, making copy-pasting from datasheets or code more of a hassle.
4. I wanted to play around with Qt.