Asyncwatch
=========

An asyncronous
[inotify](http://man7.org/linux/man-pages/man7/inotify.7.html) wrapper based on curio.


Installing
-----------

````
conda install asyncwatch -c zigzah.com/conda-pkgs
````


Usage
-----

````python
import curio

````

Requirements
-----------

- A recent enough version of the Linux Kernel (at least 2.7).
- Python >= 3.5
- [Curio](https://github.com/dabeaz/curio)

The tests require py.test.

Rationale
---------

### Why curio?

For fun mostly. Also it's significantly easier to play with than the
alternatives and has the bits required for this project.

### Why isn't it there a pip package?

At this moment the curio in pip is out of date, so it's better to get
it trough conda.

