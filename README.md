`pysb3.py` is a small, dependency-free Python module and domain-specific
language (DSL) for creating Scratch 3 project archives. It turns Python
contexts and function calls into Scratch blocks, project JSON, and a `.sb3`
ZIP archive.

It generates projects; it does **not** run them. Open the resulting project in
Scratch or TurboWarp to play it.

## What it can do

- Create a stage and sprites, with initial positions and directions.
- Build scripts from Scratch events, statements, control blocks, and reporters.
- Nest reporters inside block inputs and compose Boolean and arithmetic
  expressions.
- Add global or sprite-local variables, lists, and broadcasts.
- Include SVG costumes/backdrops and MP3 sounds in the project archive.
- Create parameterless custom blocks, or use `BaseBlock` for an opcode that
  does not have a named helper yet.
- Compile a project to a regular `.sb3` file without needing Scratch installed.

The module uses only the Python standard library. The generated project uses
Scratch 3's project format and is not a standalone HTML game.

## Requirements

- Python 3.10 or later.
- No third-party Python packages.
- Scratch or TurboWarp to open and run the generated `.sb3` project (Optional)

## Use the module

`pysb3.py` is a single-file module. Put it beside your Python script, or make
the directory containing it available on `PYTHONPATH`. For example:

```text
project/
├── pysb3.py
└── make_project.py
```

Then import the API and compile a project:

```python
from pathlib import Path
from pysb3 import Game, Stage, Sprite, When_Flag_Clicked, Forever, Move

game = Game()
stage = Stage()

with Sprite(stage, "Player", x=0, y=0, direction=90):
    @When_Flag_Clicked
    def move_player():
        with Forever():
            Move(5)

game.set_stage(stage)
game.compile(Path("my_project.sb3"))
```

`compile()` creates parent directories when needed, writes the archive, and
returns the output path. A stage is required before compiling. If no backdrop
costume is provided, the stage receives a simple default white backdrop.

### Build scripts with contexts

Use `with Sprite(...)` to select the sprite whose scripts are being built.
Event decorators such as `@When_Flag_Clicked` add an event hat and build the
decorated function's body as Scratch blocks. The function is called while
Python builds the project; it is **not** a Python callback that runs when the
project is played.

Control blocks are context managers. Put their body inside the `with` block:

```python
from pysb3 import (
    Game, Stage, Sprite, When_Flag_Clicked, Forever, If, KeyPressed,
    KEYPRESSED, Move, TurnRight,
)

game = Game()
stage = Stage()

with Sprite(stage, "Player"):
    @When_Flag_Clicked
    def control_player():
        with Forever():
            with If(KeyPressed(KEYPRESSED.SPACE)):
                Move(10)
                TurnRight(15)

game.set_stage(stage)
game.compile("player.sb3")
```

`If()` supports an `Else` branch on the context it returns. Use `IfElse()`
when a dedicated two-branch context is more convenient. Other control
contexts include `Forever()`, `Repeat(times)`, and `RepeatUntil(condition)`.

### Reporters and values

Reporter helpers return values that can be nested in statement inputs or in
other reporters:

```python
from pysb3 import (
    Game, Stage, Sprite, When_Flag_Clicked, Forever, SetX, MouseX,
    Op_Add, Number,
)

game = Game()
stage = Stage()

with Sprite(stage, "Follower"):
    @When_Flag_Clicked
    def follow_mouse():
        with Forever():
            SetX(Op_Add(MouseX(), Number(10)))

game.set_stage(stage)
game.compile("follower.sb3")
```

Use `Number(value)` and `Text(value)` when you want to explicitly identify a
numeric or text value. Numeric values must be finite; Boolean block inputs
must be reporter blocks rather than raw Python booleans.

### Costumes, backdrops, and sounds

Pass named mappings of assets when creating the stage or a sprite. Costumes
and backdrops must be SVG files; sounds must be MP3 files. Asset paths are
read when `compile()` runs, and missing files, unsupported extensions, or
invalid SVG files raise errors.

```python
from pathlib import Path
from pysb3 import Game, Stage, Sprite, Costume, Sound

assets = Path(__file__).parent / "assets"
game = Game()
stage = Stage(costumes={"Night sky": Costume(assets / "night.svg")})

ship = Sprite(
    stage,
    "Ship",
    costumes={"Ship": Costume(assets / "ship.svg")},
    sounds={"Laser": Sound(assets / "laser.mp3")},
    x=0,
    y=-120,
    direction=90,
)

game.set_stage(stage)
game.compile("ship.sb3")
```

Use `BackDrop(stage, backdrops, sounds=...)` as a context manager when you
want to build event scripts on the stage while setting its backdrops.

### Variables, lists, and broadcasts

Create these data objects before using their block helpers. Variables are
sprite-local by default; set `global_scope=True` to make a variable shared
through the stage.

```python
from pysb3 import (
    Game, Stage, Sprite, Variable, List, BroadcastMessage,
    When_Flag_Clicked, SetVariable, ChangeVariableBy, ReadVariable,
    AddToList, Say, Broadcast,
)

game = Game()
stage = Stage()
score = Variable("Score", 0, global_scope=True)
items = List("Items")
collected = BroadcastMessage("Collected")

with Sprite(stage, "Player"):
    @When_Flag_Clicked
    def start_game():
        SetVariable(score, 0)
        ChangeVariableBy(score, 1)
        AddToList("star", items)
        Say(ReadVariable(score))
        Broadcast(collected)

game.set_stage(stage)
game.compile("data.sb3")
```

Use `When_I_Receive(collected)` to create a receiver for a broadcast. A string
message name can also be used in broadcast blocks.

### Custom and not-yet-wrapped blocks

`DefineBlock(name)` and `CallBlock(name)` support **parameterless** custom
blocks:

```python
from pysb3 import Game, Stage, Sprite, When_Flag_Clicked, DefineBlock, CallBlock, Move

game = Game()
stage = Stage()

with Sprite(stage, "Walker"):
    with DefineBlock("step"):
        Move(10)

    @When_Flag_Clicked
    def start():
        CallBlock("step")

game.set_stage(stage)
game.compile("custom-block.sb3")
```

For Scratch opcodes without a named helper, `BaseBlock(opcode, inputs={...}, fields={...})` creates a context-managed block from raw Scratch 3 values.
Consult Scratch's block/opcode definitions when supplying raw inputs and
fields; `BaseBlock` does not validate that an opcode or its inputs are
supported by Scratch.

## API overview

The public API is the set of names exported by `pysb3.py`:

| Area                | Main helpers                                                                                                                                                          |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Project structure   | `Game`, `Stage`, `Sprite`, `BackDrop`                                                                                                                         |
| Assets and data     | `Costume`, `Sound`, `Variable`, `List`, `BroadcastMessage`, `Number`, `Text`                                                                            |
| Events              | `When_Flag_Clicked`, `When_Key_Pressed`, `When_Sprite_Clicked`, `When_Backdrop_Switches_To`, `When_Greater_Than`, `When_I_Receive`, `When_Clone_Starts` |
| Control             | `Forever`, `Repeat`, `If`, `IfElse`, `RepeatUntil`, `Wait`, `WaitUntil`, `StopScripts`                                                                |
| Motion              | `Move`, `TurnRight`, `TurnLeft`, `Goto`, `SetXY`, `SetX`, `SetY`, `PointInDirection`, `PointTowards`, `Glide`, `BounceOffEdge`                  |
| Looks               | `Show`, `Hide`, `Say`, `Think`, costume/backdrop switching, size, effects, and layer helpers                                                                  |
| Sound               | `PlaySound`, `StartSound`, `StopAllSounds`, volume and sound-effect helpers                                                                                     |
| Sensing             | Keyboard, mouse, timer, touching, distance, answer, attribute, and date reporters                                                                                     |
| Operators           | Arithmetic, comparisons, Boolean logic, text, random, rounding, and math reporters                                                                                    |
| Variables and lists | Read/set/change/show/hide variables; add, remove, replace, query, show, and hide list items                                                                           |
| Advanced            | `DefineBlock`, `CallBlock`, `BaseBlock`                                                                                                                         |

The module also exports enum-like collections such as `KEYPRESSED`, `GOTO`,
`ROTATION_STYLE`, `EFFECT`, `SOUND_EFFECT`, `TOUCHING`, and `DATE_PART`. See
`pysb3.py` for the full list of exported helper names and accepted arguments.

## Included examples

### Space Defender

The `game/` folder contains a mouse-aimed Space Defender project and its SVG
assets. From the repository root, run:

```powershell
py game\space_defender.py
```

This writes `game\space_defender.sb3`. Open that file in Scratch or TurboWarp.

### Ping game

The `pinggame/` folder contains a paddle-and-ball example. Run it from its
folder so its relative SVG asset paths resolve. In PowerShell:

```powershell
Set-Location pinggame
$env:PYTHONPATH = (Resolve-Path ..).Path
py example.py
```

This writes `ping.sb3` in `pinggame/`.

## TurboWarp Packager

The top-level `packager.html` is a separate, externally obtained copy of the
[TurboWarp Packager](https://github.com/TurboWarp/packager), provided here at
release **v3.14.0**. Its authors and upstream project are credited to the
TurboWarp Packager repository. Use it separately to package Scratch projects
for formats such as HTML; it is not part of `pysb3.py` and is not required to
generate `.sb3` files.

`packager.html` is third-party software and is **not** covered by this
repository's MIT license. The TurboWarp Packager is distributed under the
[Mozilla Public License 2.0 (MPL-2.0)](https://github.com/TurboWarp/packager/blob/master/LICENSE);
its copyright, license notices, and redistribution terms remain those of its
upstream authors. The MIT license below applies to the original `pysb3`
module, documentation, and project-authored examples, not to third-party
software or materials that carry separate terms.

## License

Original `pysb3` code, this documentation, and project-authored examples are
available under the [MIT License](LICENSE). Third-party software and
materials, including `packager.html`, are excluded and remain subject to
their own licenses and notices.
