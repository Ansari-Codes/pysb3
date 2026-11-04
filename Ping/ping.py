from pysb3 import *
from pathlib import Path

game = Game()
stage = Stage()
ASSETS = Path(__file__).resolve().parent / "assets"

with Sprite(
    stage,
    "ball",
    costumes={
        "ball": Costume(ASSETS / "ball.svg"),
    },
    x=0,
    y=0,
    direction=45,
):
    @When_Flag_Clicked
    def when_flag_clicked():
        with Forever():
            IfOnEdgeBounce()
            Move(10)
            with If(Touching("paddle")):
                TurnLeft(90)
            with If(Touching("bottom")):
                StopScripts()

with Sprite(
    stage,
    "paddle",
    costumes={
        "paddle": Costume(ASSETS / "paddle.svg")
    }, 
    x=0, 
    y=-170
):
    @When_Flag_Clicked
    def start():
        with Forever():
            SetX(MouseX())

Sprite(
    stage, 
    "bottom", 
    costumes={
        "bottom": Costume(ASSETS / "line.svg")
    }, 
    x=0, 
    y=-180
)

game.set_stage(stage)
game.compile("ping.sb3")
