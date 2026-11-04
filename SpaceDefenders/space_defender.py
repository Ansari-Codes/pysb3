from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pysb3 import *


ASSETS = Path(__file__).resolve().parent / "assets"
game = Game()
stage = Stage(costumes={"Starfield": Costume(ASSETS / "starfield.svg")})
score = Variable("Score", 0, global_scope=True)

with Sprite(
    stage,
    "Player",
    costumes={"Player": Costume(ASSETS / "player.svg")},
    x=0,
    y=-145,
):
    @When_Flag_Clicked
    def start_player():
        SetVariable(score, 0)
        ShowVariable(score)
        with Forever():
            Show()
            PointTowards(GOTO.MOUSE)
            with If(MouseDown()):
                CreateCloneOf("Bullet")
                Wait(0.1)

with Sprite(
    stage,
    "Enemy",
    costumes={"Enemy": Costume(ASSETS / "enemy.svg")},
    x=0,
    y=170,
):
    @When_Flag_Clicked
    def spawn_enemies():
        Hide()
        with Forever():
            Wait(1)
            SetXY(Op_Random(-220, 220), 170)
            CreateCloneOf(GOTO.MYSELF)

    @When_Clone_Starts
    def chase_player():
        Show()
        with Forever():
            PointTowards("Player")
            Move(2)
            with If(Touching("Player")):
                DeleteClone()
            with If(Touching("Bullet")):
                ChangeVariableBy(score, 1)
                DeleteClone()


with Sprite(
    stage,
    "Bullet",
    costumes={"Bullet": Costume(ASSETS / "bullet.svg")},
    x=0,
    y=-145,
):
    @When_Flag_Clicked
    def hide_bullet_source():
        Hide()

    @When_Clone_Starts
    def fly_bullet():
        Show()
        Goto("Player")
        PointTowards(GOTO.MOUSE)
        with RepeatUntil(Op_Or(Touching("Enemy"), Touching(TOUCHING.EDGE))):
            Move(12)
        DeleteClone()

game.set_stage(stage)
game.compile(Path(__file__).resolve().parent / "space_defender.sb3")
