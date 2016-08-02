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

At the moment, this is a rather straight forward (asyncronous) wrapper
over the inotify interface. This suffices for simple and can serve as
a basis for a higher level interface in the future.

````python
import tempfile

import curio

from asyncwatch import watch, EVENTS

#Create some temp file to serve as an examle
temp_dir = tempfile.mkdtemp()

#Wait until a matching set of events is
#received, and clean the resources afterwards
async def watch_once():
    async with watch(temp_dir, EVENTS.CREATE) as events:
        for event in events:
            print('Received event of type ', event.tp, 'for filename',
                  event.name)

#Watch continously
async def watch_continously():
    async for events in watch(temp_dir, (EVENTS.CLOSE, EVENTS.MODIFY)):
        for event in events:
            #Events act like bit masks
            if event.tp & EVENTS.CLOSE:
                print("Closed:" , event.name)
            elif event.tp & EVENTS.MODIFY:
                print("Modified", event.name)
            if event.name == 'done':
                print("Done watching")
                return

#Entry point for curio
async def main():
    #We wait for events and do something else meanwhile
    oneoff_task = await curio.spawn(watch_once())
    continous_task = await curio.spawn(watch_continously())


    #Like actually triggering the events
    async with curio.aopen(temp_dir+'/newfile', 'w') as f:
        await f.write("Hello")

    async with curio.aopen(temp_dir+'/done', 'w'):
        pass

    #Join the watch task
    await oneoff_task.join()
    await continous_task.join()

curio.run(main())

````

This prints:
````
Received event of type  EVENTS.CREATE for filename newfile
Modified newfile
Closed: newfile
Closed: done
Done watching
````

Requirements
-----------

- A recent enough version of the Linux Kernel (at least 2.7).
- Python >= 3.5
- A bleeding edge version of [Curio](https://github.com/dabeaz/curio).

Cloning this repository and running:

```
pip install .
```

should also work without conda.

The tests require py.test.




Rationale
---------

### Why curio?

For fun mostly. Also it's significantly easier to play with than the
alternatives and has the bits required for this project.

### Why isn't it there a pip package?

At this moment the curio in pip is out of date, so it's better to get
it trough conda.

