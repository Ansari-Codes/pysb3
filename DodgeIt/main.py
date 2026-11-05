from pysb3 import *
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"

game = Game(remove_fencing=True)
stage = Stage(width=720)

with Sprite(
    stage,
    "Player",
    costumes={
        "default": Costume(ASSETS / "ball.svg")
    },
    x = -240,
    y = 0
):
    with Forever():
        Move(5)
game.set_stage(stage)
game.compile("dodgeit.sb3")