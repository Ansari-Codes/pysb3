from __future__ import annotations

import contextvars
import hashlib
import json
import math
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from xml.etree import ElementTree

__all__ = [
    "ATTRIBUTE", "Answer", "AskAndWait", "AddToList", "BackdropNumberName",
    "BackDrop", "BaseBlock", "BounceOffEdge", "Broadcast", "BroadcastAndWait",
    "BroadcastMessage", "CallBlock", "ChangeGraphicEffectBy", "ChangeSizeBy",
    "ChangeSoundEffectBy", "ChangeVariableBy", "ChangeVolumeBy", "ChangeXBy",
    "ChangeYBy", "ClearGraphicEffects", "ClearSoundEffects", "CLONE",
    "Costume", "CostumeNumberName", "CreateCloneOf", "Current", "DATE_PART",
    "DaysSince2000", "DefineBlock", "DeleteAllOfList", "DeleteClone",
    "DeleteOfList", "Direction", "DistanceTo", "DRAG_MODE", "EFFECT",
    "Forever", "Game", "GetAttribute", "Glide", "GlideTo", "GlideToXY",
    "GREATER_THAN",     "GoBackLayers", "GoForwardBackwardLayers", "Goto", "GOTO",
    "GoToFrontBack", "Hide", "HideList",
    "HideVariable", "If", "IfElse", "IfOnEdgeBounce", "InsertAtList",
    "ItemNumberOfList", "ItemOfList", "KeyPressed", "KEYPRESSED",
    "LengthOfList", "LetterOf", "List", "ListContains", "LAYER",
    "LAYER_DIRECTION", "Loudness", "MathOp", "MATH_FUNCTION", "MouseDown",
    "MouseX", "MouseY", "Move", "NextBackdrop", "NextCostume", "Number",
    "Op_Add", "Op_And", "Op_Contains", "Op_Div", "Op_Eq", "Op_Gt",
    "Op_Join", "Op_Length", "Op_LetterOf", "Op_Lt", "Op_MathOp", "Op_Mod",
    "Op_Mul", "Op_Not", "Op_Or", "Op_Random", "Op_Round", "Op_Sub",
    "PlaySound", "PointInDirection", "PointTowards", "ReadVariable", "Repeat",
    "RepeatUntil", "ReplaceItemOfList", "ResetTimer", "ROTATION_STYLE", "Say",
    "SayForSecs", "SetDragMode", "SetGraphicEffectTo", "SetRotationStyle",
    "SetSizeTo", "SetSoundEffectTo", "SetVariable", "SetVolumeTo", "SetX",
    "SetXY", "SetY", "Show", "ShowList", "ShowVariable", "Size", "Sound",
    "SOUND_EFFECT",
    "Sprite", "Stage", "StartSound", "StopAllSounds", "StopScripts",
    "SwitchBackdropTo", "SwitchCostumeTo", "Text", "Think", "ThinkForSecs",
    "Timer", "TOUCHING",     "Touching", "TouchingColor", "TouchingColorColor", "ColorIsTouchingColor",
    "TurnLeft", "TurnRight", "Username", "Variable", "Volume", "Wait",
    "WaitUntil", "When_Backdrop_Switches_To", "When_Clone_Starts",
    "When_Flag_Clicked", "When_Greater_Than", "When_I_Receive",
    "When_Key_Pressed", "When_Sprite_Clicked", "XPosition", "YPosition",
]


_ACTIVE_SCOPE: contextvars.ContextVar[tuple["Target", list["_Block"]] | None] = (
    contextvars.ContextVar("pysb3_active_scope", default=None)
)
_DEFAULT_BACKDROP = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360">'
    '<rect width="480" height="360" fill="#ffffff"/></svg>'
)


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class Number:
    value: int | float

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("Number requires an int or float")
        if isinstance(self.value, float) and not math.isfinite(self.value):
            raise ValueError("Number must be finite")


@dataclass(frozen=True)
class Text:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("Text requires a string")


@dataclass(frozen=True)
class Costume:
    path: str | Path

    def __init__(self, path: str | Path) -> None:
        object.__setattr__(self, "path", path)


@dataclass(frozen=True)
class Sound:
    path: str | Path

    def __init__(self, path: str | Path) -> None:
        object.__setattr__(self, "path", path)


@dataclass
class _Asset:
    name: str
    data: bytes
    data_format: str
    asset_id: str
    rotation_center_x: float = 0
    rotation_center_y: float = 0
    bitmap_resolution: int = 1

    @property
    def md5ext(self) -> str:
        return f"{self.asset_id}.{self.data_format}"

    def sound_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "assetId": self.asset_id,
            "dataFormat": self.data_format,
            "format": "",
            "rate": 44100,
            "sampleCount": 0,
            "md5ext": self.md5ext,
        }


def _read_asset(name: str, value: Costume | Sound, is_costume: bool) -> _Asset:
    path = Path(value.path)
    if not path.is_file():
        raise FileNotFoundError(f"Asset file does not exist: {path}")
    expected_extension = ".svg" if is_costume else ".mp3"
    if path.suffix.lower() != expected_extension:
        kind = "costumes" if is_costume else "sounds"
        raise ValueError(f"{kind} must use {expected_extension} files: {path}")
    data = path.read_bytes()
    asset_id = hashlib.md5(data).hexdigest()
    if is_costume:
        try:
            root = ElementTree.fromstring(data)
        except ElementTree.ParseError as error:
            raise ValueError(f"Invalid SVG costume: {path}") from error
        width, height = _svg_dimensions(root)
        return _Asset(name, data, "svg", asset_id, width / 2, height / 2)
    return _Asset(name, data, "mp3", asset_id)


def _svg_dimensions(root: ElementTree.Element) -> tuple[float, float]:
    def dimension(name: str) -> float | None:
        raw = root.attrib.get(name)
        if raw is None:
            return None
        match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)", raw)
        return float(match.group(1)) if match else None

    width, height = dimension("width"), dimension("height")
    if width is not None and height is not None:
        return width, height
    view_box = root.attrib.get("viewBox", "").replace(",", " ").split()
    if len(view_box) == 4:
        try:
            return float(view_box[2]), float(view_box[3])
        except ValueError:
            pass
    return 480, 360


@dataclass
class _Input:
    value: Any
    kind: str = "auto"
    menu_opcode: str | None = None
    menu_field: str | None = None


@dataclass
class _Block:
    opcode: str
    inputs: dict[str, _Input] = field(default_factory=dict)
    fields: dict[str, Any] = field(default_factory=dict)
    body: list["_Block"] = field(default_factory=list)
    else_body: list["_Block"] = field(default_factory=list)
    body_as_substack: bool = True
    mutation: dict[str, Any] | None = None
    procedure_name: str | None = None
    block_id: str = field(default_factory=_new_id)


@dataclass(frozen=True)
class _Reporter:
    opcode: str
    inputs: Mapping[str, _Input] = field(default_factory=dict)
    fields: Mapping[str, Any] = field(default_factory=dict)


def _scope() -> tuple["Target", list[_Block]]:
    active = _ACTIVE_SCOPE.get()
    if active is None:
        raise RuntimeError("Blocks can only be used inside a sprite or event script")
    return active


class _BlockContext:
    def __init__(
        self,
        opcode: str,
        inputs: Mapping[str, _Input] | None = None,
        fields: Mapping[str, Any] | None = None,
        *,
        allow_else: bool = False,
    ) -> None:
        self._block = _Block(opcode, dict(inputs or {}), dict(fields or {}))
        self._allow_else = allow_else
        self._token: contextvars.Token | None = None

    def __enter__(self) -> "_BlockContext":
        _, statements = _scope()
        statements.append(self._block)
        self._token = _ACTIVE_SCOPE.set((_scope()[0], self._block.body))
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self._token is not None:
            _ACTIVE_SCOPE.reset(self._token)
        return False

    @property
    def Else(self) -> "_ElseContext":
        if not self._allow_else:
            raise AttributeError("This block has no Else branch")
        return _ElseContext(self._block)


class _ElseContext:
    def __init__(self, block: _Block) -> None:
        self._block = block
        self._token: contextvars.Token | None = None

    def __enter__(self) -> "_ElseContext":
        target, _ = _scope()
        if self._block.opcode == "control_if":
            self._block.opcode = "control_if_else"
            self._block.inputs["SUBSTACK2"] = _Input(None, "substack_else")
        self._token = _ACTIVE_SCOPE.set((target, self._block.else_body))
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        if self._token is not None:
            _ACTIVE_SCOPE.reset(self._token)
        return False


class BaseBlock(_BlockContext):
    """Create a context-managed block from a Scratch 3 opcode and raw inputs."""

    def __init__(
        self,
        opcode: str,
        inputs: Mapping[str, Any] | None = None,
        fields: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            opcode,
            {name: _Input(value) for name, value in (inputs or {}).items()},
            fields,
        )


def _statement(
    opcode: str,
    inputs: Mapping[str, _Input] | None = None,
    fields: Mapping[str, Any] | None = None,
) -> _BlockContext:
    return _BlockContext(opcode, inputs, fields)


def _emit(
    opcode: str,
    inputs: Mapping[str, _Input] | None = None,
    fields: Mapping[str, Any] | None = None,
) -> None:
    _, statements = _scope()
    statements.append(_Block(opcode, dict(inputs or {}), dict(fields or {})))


def _reporter(
    opcode: str,
    inputs: Mapping[str, _Input] | None = None,
    fields: Mapping[str, Any] | None = None,
) -> _Reporter:
    return _Reporter(opcode, inputs or {}, fields or {})


def _input(value: Any, kind: str = "auto") -> _Input:
    return _Input(value, kind)


class _EnumValues:
    def __init__(self, values: Mapping[str, str]) -> None:
        for name, value in values.items():
            setattr(self, name, value)


def _enum(**values: str) -> _EnumValues:
    return _EnumValues(values)


KEYPRESSED = _EnumValues(
    {
        "SPACE": "space",
        "UP": "up arrow",
        "DOWN": "down arrow",
        "LEFT": "left arrow",
        "RIGHT": "right arrow",
        **{f"_{letter}": letter for letter in "abcdefghijklmnopqrstuvwxyz"},
        **{f"_{digit}": digit for digit in "0123456789"},
    }
)
GOTO = _EnumValues({"MOUSE": "_mouse_", "RANDOM": "_random_", "MYSELF": "_myself_"})
ROTATION_STYLE = _enum(ALL_AROUND="all around", LEFT_RIGHT="left-right", DONT_ROTATE="don't rotate")
EFFECT = _enum(COLOR="COLOR", FISHEYE="FISHEYE", WHIRL="WHIRL", PIXELATE="PIXELATE",
               MOSAIC="MOSAIC", BRIGHTNESS="BRIGHTNESS", GHOST="GHOST")
SOUND_EFFECT = _enum(PITCH="PITCH", PAN="PAN")
LAYER = _enum(FRONT="front", BACK="back")
LAYER_DIRECTION = _enum(FORWARD="forward", BACKWARD="backward")
CLONE = _enum(MYSELF="_myself_")
TOUCHING = _enum(MOUSE="_mouse_", EDGE="_edge_")
DATE_PART = _enum(YEAR="YEAR", MONTH="MONTH", DATE="DATE", DAY_OF_WEEK="DAYOFWEEK",
                  HOUR="HOUR", MINUTE="MINUTE", SECOND="SECOND")
ATTRIBUTE = _enum(X_POSITION="x position", Y_POSITION="y position",
                  DIRECTION="direction", COSTUME="costume #", COSTUME_NAME="costume name",
                  SIZE="size", VOLUME="volume", BACKDROP="backdrop #",
                  BACKDROP_NAME="backdrop name")
DRAG_MODE = _enum(DRAGGABLE="draggable", NOT_DRAGGABLE="not draggable")
GREATER_THAN = _enum(LOUDNESS="LOUDNESS", TIMER="TIMER")
MATH_FUNCTION = _enum(
    ABS="abs", FLOOR="floor", CEILING="ceiling", SQRT="sqrt", SIN="sin", COS="cos",
    TAN="tan", ASIN="asin", ACOS="acos", ATAN="atan", LN="ln", LOG="log",
    E="e ^", TEN="10 ^",
)


@dataclass(frozen=True)
class Variable:
    name: str
    value: Any = 0
    variable_id: str = field(default_factory=_new_id)
    global_scope: bool = False


@dataclass(frozen=True)
class List:
    name: str
    items: tuple[Any, ...] = ()
    list_id: str = field(default_factory=_new_id)

    def __init__(self, name: str, items: Iterable[Any] = ()) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "list_id", _new_id())


@dataclass(frozen=True)
class BroadcastMessage:
    name: str
    broadcast_id: str = field(default_factory=_new_id)


def _variable_field(variable: Variable) -> tuple[str, str]:
    target, _ = _scope()
    owner = target.stage if variable.global_scope and isinstance(target, Sprite) else target
    owner.variables.setdefault(variable.variable_id, [variable.name, variable.value])
    return variable.name, variable.variable_id


def _list_field(value: List) -> tuple[str, str]:
    target, _ = _scope()
    target.lists.setdefault(value.list_id, [value.name, list(value.items)])
    return value.name, value.list_id


def _broadcast_field(value: BroadcastMessage) -> tuple[str, str]:
    target, _ = _scope()
    owner = target.stage if isinstance(target, Sprite) else target
    owner.broadcasts.setdefault(value.broadcast_id, value.name)
    return value.name, value.broadcast_id


def _get_broadcast(value: BroadcastMessage | str) -> BroadcastMessage:
    target, _ = _scope()
    owner = target.stage if isinstance(target, Sprite) else target
    name = value.name if isinstance(value, BroadcastMessage) else str(value)
    if isinstance(value, BroadcastMessage) and value.broadcast_id not in owner.broadcasts:
        existing_id = next(
            (broadcast_id for broadcast_id, broadcast_name in owner.broadcasts.items()
             if broadcast_name == name),
            None,
        )
        if existing_id is not None:
            return BroadcastMessage(name, existing_id)
        return value
    existing_id = next(
        (broadcast_id for broadcast_id, broadcast_name in owner.broadcasts.items()
         if broadcast_name == name),
        None,
    )
    return BroadcastMessage(name, existing_id or _new_id())


def _as_field(value: Any) -> Any:
    if isinstance(value, Variable):
        return _variable_field(value)
    if isinstance(value, List):
        return _list_field(value)
    if isinstance(value, BroadcastMessage):
        return _broadcast_field(value)
    return value


def _menu_input(value: Any, opcode: str, field_name: str) -> _Input:
    return _Input(value, "menu", opcode, field_name)


def _color_input(value: Any, field_name: str = "COLOUR") -> _Input:
    return _menu_input(value, "colour_picker", field_name)


def _event(opcode: str, fields: Mapping[str, Any] | None = None) -> Callable:
    def decorate(function: Callable) -> Callable:
        target, _ = _scope()
        event_fields = {name: _as_field(value) for name, value in (fields or {}).items()}
        block = _Block(opcode, fields=event_fields, body_as_substack=False)
        target.blocks.append(block)
        token = _ACTIVE_SCOPE.set((target, block.body))
        try:
            function()
        finally:
            _ACTIVE_SCOPE.reset(token)
        return function

    return decorate


def When_Flag_Clicked(function: Callable) -> Callable:
    return _event("event_whenflagclicked")(function)


def When_Key_Pressed(key: str) -> Callable:
    return _event("event_whenkeypressed", {"KEY_OPTION": key})


def When_Sprite_Clicked(function: Callable) -> Callable:
    return _event("event_whenthisspriteclicked")(function)


def When_Backdrop_Switches_To(backdrop: Any) -> Callable:
    return _event("event_whenbackdropswitchesto", {"BACKDROP": backdrop})


def When_Greater_Than(sensor: Any, value: Any) -> Callable:
    def decorate(function: Callable) -> Callable:
        target, _ = _scope()
        block = _Block(
            "event_whengreaterthan",
            inputs={"VALUE": _input(value, "number")},
            fields={"WHENGREATERTHANMENU": sensor},
            body_as_substack=False,
        )
        target.blocks.append(block)
        token = _ACTIVE_SCOPE.set((target, block.body))
        try:
            function()
        finally:
            _ACTIVE_SCOPE.reset(token)
        return function

    return decorate


def When_I_Receive(message: BroadcastMessage | str) -> Callable:
    return _event("event_whenbroadcastreceived", {"BROADCAST_OPTION": _get_broadcast(message)})


def When_Clone_Starts(function: Callable) -> Callable:
    return _event("control_start_as_clone")(function)


def Forever() -> _BlockContext:
    return _statement("control_forever", {"SUBSTACK": _input(None, "substack")})


def Repeat(times: Any) -> _BlockContext:
    return _statement(
        "control_repeat",
        {"TIMES": _input(times, "integer"), "SUBSTACK": _input(None, "substack")},
    )


def If(condition: Any) -> _BlockContext:
    return _BlockContext(
        "control_if",
        {"CONDITION": _input(condition, "boolean"), "SUBSTACK": _input(None, "substack")},
        allow_else=True,
    )


def IfElse(condition: Any) -> _BlockContext:
    return _BlockContext(
        "control_if_else",
        {
            "CONDITION": _input(condition, "boolean"),
            "SUBSTACK": _input(None, "substack"),
            "SUBSTACK2": _input(None, "substack_else"),
        },
    )


def Wait(seconds: Any) -> None:
    _emit("control_wait", {"DURATION": _input(seconds, "positive")})


def Move(steps: Any) -> None:
    _emit("motion_movesteps", {"STEPS": _input(steps, "number")})


def TurnRight(degrees: Any) -> None:
    _emit("motion_turnright", {"DEGREES": _input(degrees, "number")})


def TurnLeft(degrees: Any) -> None:
    _emit("motion_turnleft", {"DEGREES": _input(degrees, "number")})


def Goto(target: Any) -> None:
    _emit(
        "motion_goto",
        {
            "TO": _Input(
                target,
                "menu",
                "motion_goto_menu",
                "TO",
            )
        },
    )


def SetXY(x: Any, y: Any) -> None:
    _emit(
        "motion_gotoxy",
        {"X": _input(x, "number"), "Y": _input(y, "number")},
    )


def Say(message: Any) -> None:
    _emit("looks_say", {"MESSAGE": _input(message, "text")})


def Show() -> None:
    _emit("looks_show")


def Hide() -> None:
    _emit("looks_hide")


def Glide(seconds: Any, target: Any) -> None:
    _emit(
        "motion_glideto",
        {
            "SECS": _input(seconds, "positive"),
            "TO": _menu_input(target, "motion_glideto_menu", "TO"),
        },
    )


def GlideTo(seconds: Any, target: Any) -> None:
    Glide(seconds, target)


def GlideToXY(seconds: Any, x: Any, y: Any) -> None:
    _emit(
        "motion_glidesecstoxy",
        {
            "SECS": _input(seconds, "positive"),
            "X": _input(x, "number"),
            "Y": _input(y, "number"),
        },
    )


def PointInDirection(direction: Any) -> None:
    _emit("motion_pointindirection", {"DIRECTION": _input(direction, "angle")})


def PointTowards(target: Any) -> None:
    _emit(
        "motion_pointtowards",
        {"TOWARDS": _menu_input(target, "motion_pointtowards_menu", "TOWARDS")},
    )


def ChangeXBy(amount: Any) -> None:
    _emit("motion_changexby", {"DX": _input(amount, "number")})


def SetX(value: Any) -> None:
    _emit("motion_setx", {"X": _input(value, "number")})


def ChangeYBy(amount: Any) -> None:
    _emit("motion_changeyby", {"DY": _input(amount, "number")})


def SetY(value: Any) -> None:
    _emit("motion_sety", {"Y": _input(value, "number")})


def BounceOffEdge() -> None:
    _emit("motion_ifonedgebounce")


def IfOnEdgeBounce() -> None:
    BounceOffEdge()


def SetRotationStyle(style: str) -> None:
    _emit("motion_setrotationstyle", fields={"STYLE": style})


def XPosition() -> _Reporter:
    return _reporter("motion_xposition")


def YPosition() -> _Reporter:
    return _reporter("motion_yposition")


def Direction() -> _Reporter:
    return _reporter("motion_direction")


def SayForSecs(message: Any, seconds: Any) -> None:
    _emit(
        "looks_sayforsecs",
        {"MESSAGE": _input(message, "text"), "SECS": _input(seconds, "positive")},
    )


def ThinkForSecs(message: Any, seconds: Any) -> None:
    _emit(
        "looks_thinkforsecs",
        {"MESSAGE": _input(message, "text"), "SECS": _input(seconds, "positive")},
    )


def Think(message: Any) -> None:
    _emit("looks_think", {"MESSAGE": _input(message, "text")})


def SwitchCostumeTo(costume: Any) -> None:
    _emit(
        "looks_switchcostumeto",
        {"COSTUME": _menu_input(costume, "looks_costume", "COSTUME")},
    )


def NextCostume() -> None:
    _emit("looks_nextcostume")


def SwitchBackdropTo(backdrop: Any) -> None:
    _emit(
        "looks_switchbackdropto",
        {"BACKDROP": _menu_input(backdrop, "looks_backdrops", "BACKDROP")},
    )


def NextBackdrop() -> None:
    _emit("looks_nextbackdrop")


def ChangeSizeBy(amount: Any) -> None:
    _emit("looks_changesizeby", {"CHANGE": _input(amount, "number")})


def SetSizeTo(percent: Any) -> None:
    _emit("looks_setsizeto", {"SIZE": _input(percent, "number")})


def ChangeGraphicEffectBy(effect: Any, amount: Any) -> None:
    _emit(
        "looks_changeeffectby",
        {"EFFECT": _input(effect, "text"), "CHANGE": _input(amount, "number")},
    )


def SetGraphicEffectTo(effect: Any, value: Any) -> None:
    _emit(
        "looks_seteffectto",
        {"EFFECT": _input(effect, "text"), "VALUE": _input(value, "number")},
    )


def ClearGraphicEffects() -> None:
    _emit("looks_cleargraphiceffects")


def GoToFrontBack(layer: Any) -> None:
    _emit("looks_gotofrontback", fields={"FRONT_BACK": layer})


def GoBackLayers(layers: Any, direction: Any = "backward") -> None:
    _emit(
        "looks_goforwardbackwardlayers",
        {"NUM": _input(layers, "integer")},
        {"FORWARD_BACKWARD": direction},
    )


def GoForwardBackwardLayers(layers: Any, direction: Any) -> None:
    GoBackLayers(layers, direction)


def CostumeNumberName(mode: Any = "number") -> _Reporter:
    return _reporter("looks_costumenumbername", fields={"NUMBER_NAME": mode})


def BackdropNumberName(mode: Any = "number") -> _Reporter:
    return _reporter("looks_backdropnumbername", fields={"NUMBER_NAME": mode})


def Size() -> _Reporter:
    return _reporter("looks_size")


def PlaySound(sound: Any) -> None:
    _emit(
        "sound_playuntildone",
        {"SOUND_MENU": _menu_input(sound, "sound_sounds_menu", "SOUND_MENU")},
    )


def StartSound(sound: Any) -> None:
    _emit(
        "sound_play",
        {"SOUND_MENU": _menu_input(sound, "sound_sounds_menu", "SOUND_MENU")},
    )


def StopAllSounds() -> None:
    _emit("sound_stopallsounds")


def ChangeSoundEffectBy(effect: Any, amount: Any) -> None:
    _emit(
        "sound_changeeffectby",
        {"EFFECT": _input(effect, "text"), "VALUE": _input(amount, "number")},
    )


def SetSoundEffectTo(effect: Any, value: Any) -> None:
    _emit(
        "sound_seteffectto",
        {"EFFECT": _input(effect, "text"), "VALUE": _input(value, "number")},
    )


def ClearSoundEffects() -> None:
    _emit("sound_cleareffects")


def ChangeVolumeBy(amount: Any) -> None:
    _emit("sound_changevolumeby", {"VOLUME": _input(amount, "number")})


def SetVolumeTo(percent: Any) -> None:
    _emit("sound_setvolumeto", {"VOLUME": _input(percent, "number")})


def Volume() -> _Reporter:
    return _reporter("sound_volume")


def KeyPressed(key: Any) -> _Reporter:
    return _reporter(
        "sensing_keypressed",
        {
            "KEY_OPTION": _Input(
                key, "menu", "sensing_keyoptions", "KEY_OPTION"
            )
        },
    )


def Broadcast(message: BroadcastMessage | str) -> None:
    value = _get_broadcast(message)
    field_value = _broadcast_field(value)
    _emit(
        "event_broadcast",
        {"BROADCAST_OPTION": _menu_input(field_value, "event_broadcast_menu", "BROADCAST_OPTION")},
    )


def BroadcastAndWait(message: BroadcastMessage | str) -> None:
    value = _get_broadcast(message)
    field_value = _broadcast_field(value)
    _emit(
        "event_broadcastandwait",
        {"BROADCAST_OPTION": _menu_input(field_value, "event_broadcast_menu", "BROADCAST_OPTION")},
    )


def WaitUntil(condition: Any) -> None:
    _emit("control_wait_until", {"CONDITION": _input(condition, "boolean")})


def RepeatUntil(condition: Any) -> _BlockContext:
    return _statement(
        "control_repeat_until",
        {"CONDITION": _input(condition, "boolean"), "SUBSTACK": _input(None, "substack")},
    )


def StopScripts(option: Any = "all") -> None:
    _emit("control_stop", fields={"STOP_OPTION": option})


def CreateCloneOf(target: Any = "_myself_") -> None:
    _emit(
        "control_create_clone_of",
        {"CLONE_OPTION": _menu_input(target, "control_create_clone_of_menu", "CLONE_OPTION")},
    )


def DeleteClone() -> None:
    _emit("control_delete_this_clone")


def Touching(target: Any) -> _Reporter:
    return _reporter(
        "sensing_touchingobject",
        {"TOUCHINGOBJECTMENU": _menu_input(target, "sensing_touchingobjectmenu", "TOUCHINGOBJECTMENU")},
    )


def TouchingColor(color: Any) -> _Reporter:
    return _reporter("sensing_touchingcolor", {"COLOR": _color_input(color)})


def TouchingColorColor(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "sensing_coloristouchingcolor",
        {"COLOR": _color_input(first), "COLOR2": _color_input(second)},
    )


def ColorIsTouchingColor(first: Any, second: Any) -> _Reporter:
    return TouchingColorColor(first, second)


def DistanceTo(target: Any) -> _Reporter:
    return _reporter(
        "sensing_distanceto",
        {"DISTANCETOMENU": _menu_input(target, "sensing_distancetomenu", "DISTANCETOMENU")},
    )


def AskAndWait(question: Any) -> None:
    _emit("sensing_askandwait", {"QUESTION": _input(question, "text")})


def Answer() -> _Reporter:
    return _reporter("sensing_answer")


def MouseDown() -> _Reporter:
    return _reporter("sensing_mousedown")


def MouseX() -> _Reporter:
    return _reporter("sensing_mousex")


def MouseY() -> _Reporter:
    return _reporter("sensing_mousey")


def SetDragMode(mode: Any) -> None:
    _emit(
        "sensing_setdragmode",
        {"DRAG_MODE": _menu_input(mode, "sensing_setdragmode_menu", "DRAG_MODE")},
    )


def Loudness() -> _Reporter:
    return _reporter("sensing_loudness")


def Timer() -> _Reporter:
    return _reporter("sensing_timer")


def ResetTimer() -> None:
    _emit("sensing_resettimer")


def GetAttribute(attribute: Any, target: Any) -> _Reporter:
    return _reporter(
        "sensing_of",
        {
            "PROPERTY": _menu_input(attribute, "sensing_of_property_menu", "PROPERTY"),
            "OBJECT": _menu_input(target, "sensing_of_object_menu", "OBJECT"),
        },
    )


def Current(part: Any) -> _Reporter:
    return _reporter(
        "sensing_current",
        {"CURRENTMENU": _menu_input(part, "sensing_currentmenu", "CURRENTMENU")},
    )


def DaysSince2000() -> _Reporter:
    return _reporter("sensing_dayssince2000")


def Username() -> _Reporter:
    return _reporter("sensing_username")


def LetterOf(index: Any, text: Any) -> _Reporter:
    return _reporter(
        "operator_letter_of",
        {"LETTER": _input(index, "integer"), "STRING": _input(text, "text")},
    )


def Op_LetterOf(index: Any, text: Any) -> _Reporter:
    return LetterOf(index, text)


def Op_Length(text: Any) -> _Reporter:
    return _reporter("operator_length", {"STRING": _input(text, "text")})


def Op_Contains(text: Any, item: Any) -> _Reporter:
    return _reporter(
        "operator_contains",
        {"STRING1": _input(text, "text"), "STRING2": _input(item, "text")},
    )


def Op_Round(value: Any) -> _Reporter:
    return _reporter("operator_round", {"NUM": _input(value, "number")})


def MathOp(operator: Any, value: Any) -> _Reporter:
    return _reporter(
        "operator_mathop",
        {
            "OPERATOR": _menu_input(operator, "operator_mathop_menu", "OPERATOR"),
            "NUM": _input(value, "number"),
        },
    )


def Op_MathOp(operator: Any, value: Any) -> _Reporter:
    return MathOp(operator, value)


def ReadVariable(variable: Variable) -> _Reporter:
    return _reporter("data_variable", fields={"VARIABLE": _variable_field(variable)})


def SetVariable(variable: Variable, value: Any) -> None:
    _emit(
        "data_setvariableto",
        {"VALUE": _input(value)},
        {"VARIABLE": _variable_field(variable)},
    )


def ChangeVariableBy(variable: Variable, amount: Any) -> None:
    _emit(
        "data_changevariableby",
        {"VALUE": _input(amount, "number")},
        {"VARIABLE": _variable_field(variable)},
    )


def ShowVariable(variable: Variable) -> None:
    _emit("data_showvariable", fields={"VARIABLE": _variable_field(variable)})


def HideVariable(variable: Variable) -> None:
    _emit("data_hidevariable", fields={"VARIABLE": _variable_field(variable)})


def AddToList(item: Any, value: List) -> None:
    _emit("data_addtolist", {"ITEM": _input(item)}, {"LIST": _list_field(value)})


def DeleteOfList(index: Any, value: List) -> None:
    _emit(
        "data_deleteoflist",
        {"INDEX": _input(index, "integer")},
        {"LIST": _list_field(value)},
    )


def DeleteAllOfList(value: List) -> None:
    _emit("data_deletealloflist", fields={"LIST": _list_field(value)})


def InsertAtList(item: Any, index: Any, value: List) -> None:
    _emit(
        "data_insertatlist",
        {"ITEM": _input(item), "INDEX": _input(index, "integer")},
        {"LIST": _list_field(value)},
    )


def ReplaceItemOfList(index: Any, value: List, item: Any) -> None:
    _emit(
        "data_replaceitemoflist",
        {"INDEX": _input(index, "integer"), "ITEM": _input(item)},
        {"LIST": _list_field(value)},
    )


def ItemOfList(index: Any, value: List) -> _Reporter:
    return _reporter(
        "data_itemoflist",
        {"INDEX": _input(index, "integer")},
        {"LIST": _list_field(value)},
    )


def ItemNumberOfList(item: Any, value: List) -> _Reporter:
    return _reporter(
        "data_itemnumoflist",
        {"ITEM": _input(item, "text")},
        {"LIST": _list_field(value)},
    )


def LengthOfList(value: List) -> _Reporter:
    return _reporter("data_lengthoflist", fields={"LIST": _list_field(value)})


def ListContains(value: List, item: Any) -> _Reporter:
    return _reporter(
        "data_listcontainsitem",
        {"ITEM": _input(item, "text")},
        {"LIST": _list_field(value)},
    )


def ShowList(value: List) -> None:
    _emit("data_showlist", fields={"LIST": _list_field(value)})


def HideList(value: List) -> None:
    _emit("data_hidelist", fields={"LIST": _list_field(value)})


def DefineBlock(name: str) -> _BlockContext:
    mutation = {
        "tagName": "mutation",
        "children": [],
        "proccode": name,
        "argumentids": "[]",
        "warp": "false",
    }
    block = _BlockContext("procedures_definition")
    block._block.mutation = mutation
    block._block.procedure_name = name
    block._block.body_as_substack = False
    return block


def CallBlock(name: str) -> None:
    _, statements = _scope()
    statements.append(
        _Block(
            "procedures_call",
            mutation={
                "tagName": "mutation",
                "children": [],
                "proccode": name,
                "argumentids": "[]",
                "warp": "false",
            },
            procedure_name=name,
        )
    )


def Op_Add(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_add",
        {"NUM1": _input(first, "number"), "NUM2": _input(second, "number")},
    )


def Op_Sub(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_subtract",
        {"NUM1": _input(first, "number"), "NUM2": _input(second, "number")},
    )


def Op_Mul(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_multiply",
        {"NUM1": _input(first, "number"), "NUM2": _input(second, "number")},
    )


def Op_Div(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_divide",
        {"NUM1": _input(first, "number"), "NUM2": _input(second, "number")},
    )


def Op_Mod(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_mod",
        {"NUM1": _input(first, "number"), "NUM2": _input(second, "number")},
    )


def Op_Random(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_random",
        {"FROM": _input(first, "number"), "TO": _input(second, "number")},
    )


def Op_Lt(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_lt",
        {"OPERAND1": _input(first, "text"), "OPERAND2": _input(second, "text")},
    )


def Op_Gt(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_gt",
        {"OPERAND1": _input(first, "text"), "OPERAND2": _input(second, "text")},
    )


def Op_Eq(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_equals",
        {"OPERAND1": _input(first, "text"), "OPERAND2": _input(second, "text")},
    )


def Op_And(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_and",
        {
            "OPERAND1": _input(first, "boolean"),
            "OPERAND2": _input(second, "boolean"),
        },
    )


def Op_Or(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_or",
        {
            "OPERAND1": _input(first, "boolean"),
            "OPERAND2": _input(second, "boolean"),
        },
    )


def Op_Not(value: Any) -> _Reporter:
    return _reporter("operator_not", {"OPERAND": _input(value, "boolean")})


def Op_Join(first: Any, second: Any) -> _Reporter:
    return _reporter(
        "operator_join",
        {"STRING1": _input(first, "text"), "STRING2": _input(second, "text")},
    )


class Target:
    def __init__(
        self,
        name: str,
        costumes: Mapping[str, Costume] | None = None,
        sounds: Mapping[str, Sound] | None = None,
    ) -> None:
        self.name = name
        self.blocks: list[_Block] = []
        self.costumes = dict(costumes or {})
        self.sounds = dict(sounds or {})
        self.variables: dict[str, list[Any]] = {}
        self.lists: dict[str, list[Any]] = {}
        self.broadcasts: dict[str, str] = {}

    def _assets(self) -> tuple[list[_Asset], list[_Asset]]:
        costumes = [
            _read_asset(name, costume, True)
            for name, costume in self.costumes.items()
        ]
        sounds = [
            _read_asset(name, sound, False) for name, sound in self.sounds.items()
        ]
        return costumes, sounds


class Stage(Target):
    def __init__(
        self,
        costumes: Mapping[str, Costume] | None = None,
        sounds: Mapping[str, Sound] | None = None,
    ) -> None:
        super().__init__("Stage", costumes, sounds)
        self.sprites: list[Sprite] = []

    def _assets(self) -> tuple[list[_Asset], list[_Asset]]:
        if not self.costumes:
            data = _DEFAULT_BACKDROP.encode("utf-8")
            asset = _Asset(
                "backdrop1",
                data,
                "svg",
                hashlib.md5(data).hexdigest(),
                240,
                180,
            )
            costumes = [asset]
        else:
            costumes = [
                _read_asset(name, costume, True)
                for name, costume in self.costumes.items()
            ]
        sounds = [
            _read_asset(name, sound, False) for name, sound in self.sounds.items()
        ]
        return costumes, sounds


class Sprite(Target):
    def __init__(
        self,
        stage: Stage,
        name: str,
        costumes: Mapping[str, Costume] | None = None,
        sounds: Mapping[str, Sound] | None = None,
        x: int | float = 0,
        y: int | float = 0,
        direction: int | float = 90,
    ) -> None:
        if not isinstance(stage, Stage):
            raise TypeError("Sprite requires a Stage")
        super().__init__(name, costumes, sounds)
        self.stage = stage
        self.x, self.y, self.direction = x, y, direction
        stage.sprites.append(self)

    def __enter__(self) -> "Sprite":
        self._token = _ACTIVE_SCOPE.set((self, self.blocks))
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        _ACTIVE_SCOPE.reset(self._token)
        return False

    def _assets(self) -> tuple[list[_Asset], list[_Asset]]:
        if self.costumes:
            costumes = [
                _read_asset(name, costume, True)
                for name, costume in self.costumes.items()
            ]
        else:
            data = _DEFAULT_BACKDROP.encode("utf-8")
            costumes = [
                _Asset(
                    "costume1",
                    data,
                    "svg",
                    hashlib.md5(data).hexdigest(),
                    240,
                    180,
                )
            ]
        sounds = [
            _read_asset(name, sound, False) for name, sound in self.sounds.items()
        ]
        return costumes, sounds


class BackDrop:
    def __init__(
        self,
        stage: Stage,
        backdrops: Mapping[str, Costume],
        sounds: Mapping[str, Sound] | None = None,
        **_: Any,
    ) -> None:
        if not isinstance(stage, Stage):
            raise TypeError("BackDrop requires a Stage")
        stage.costumes = dict(backdrops)
        if sounds is not None:
            stage.sounds = dict(sounds)
        self.stage = stage

    def __enter__(self) -> "BackDrop":
        self._token = _ACTIVE_SCOPE.set((self.stage, self.stage.blocks))
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        _ACTIVE_SCOPE.reset(self._token)
        return False


class Game:
    def __init__(self) -> None:
        self.stage: Stage | None = None
        self.backdrop: BackDrop | None = None

    def set_stage(self, stage: Stage) -> None:
        if not isinstance(stage, Stage):
            raise TypeError("set_stage expects a Stage")
        self.stage = stage

    def set_backdrop(self, backdrop: BackDrop) -> None:
        if not isinstance(backdrop, BackDrop):
            raise TypeError("set_backdrop expects a BackDrop")
        self.backdrop = backdrop
        self.stage = backdrop.stage

    def compile(self, filename: str | Path) -> Path:
        if self.stage is None:
            raise ValueError("Set a stage before compiling the game")
        output_path = Path(filename)
        targets, assets = _serialize_game(self.stage)
        project = {
            "targets": targets,
            "monitors": [],
            "extensions": [],
            "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "pysb3"},
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "project.json",
                json.dumps(project, ensure_ascii=False, separators=(",", ":")),
            )
            for asset_name, data in assets.items():
                archive.writestr(asset_name, data)
        return output_path


def _serialize_game(stage: Stage) -> tuple[list[dict[str, Any]], dict[str, bytes]]:
    targets: list[dict[str, Any]] = []
    assets: dict[str, bytes] = {}
    stage_target = _serialize_target(stage, True, 0)
    targets.append(stage_target[0])
    assets.update(stage_target[1])
    for index, sprite in enumerate(stage.sprites, start=1):
        sprite_target = _serialize_target(sprite, False, index)
        targets.append(sprite_target[0])
        assets.update(sprite_target[1])
    return targets, assets


def _serialize_target(
    target: Target, is_stage: bool, layer_order: int
) -> tuple[dict[str, Any], dict[str, bytes]]:
    costumes, sounds = target._assets()
    blocks: dict[str, dict[str, Any]] = {}
    for index, top_block in enumerate(target.blocks):
        _serialize_block(
            top_block,
            blocks,
            parent=None,
            top_level=True,
            x=40,
            y=40 + index * 90,
        )
    target_json: dict[str, Any] = {
        "isStage": is_stage,
        "name": target.name,
        "variables": target.variables,
        "lists": target.lists,
        "broadcasts": target.broadcasts,
        "blocks": blocks,
        "comments": {},
        "currentCostume": 0,
        "costumes": [_costume_json(asset) for asset in costumes],
        "sounds": [asset.sound_json() for asset in sounds],
        "volume": 100,
        "layerOrder": layer_order,
    }
    if is_stage:
        target_json.update(
            {
                "tempo": 60,
                "videoTransparency": 50,
                "videoState": "on",
                "textToSpeechLanguage": None,
            }
        )
    else:
        target_json.update(
            {
                "visible": True,
                "x": target.x,
                "y": target.y,
                "size": 100,
                "direction": target.direction,
                "draggable": False,
                "rotationStyle": "all around",
            }
        )
    content = {asset.md5ext: asset.data for asset in [*costumes, *sounds]}
    return target_json, content


def _costume_json(asset: _Asset) -> dict[str, Any]:
    return {
        "name": asset.name,
        "bitmapResolution": asset.bitmap_resolution,
        "dataFormat": asset.data_format,
        "assetId": asset.asset_id,
        "md5ext": asset.md5ext,
        "rotationCenterX": asset.rotation_center_x,
        "rotationCenterY": asset.rotation_center_y,
    }


def _serialize_block(
    block: _Block,
    blocks: dict[str, dict[str, Any]],
    *,
    parent: str | None,
    top_level: bool,
    x: int | None = None,
    y: int | None = None,
) -> str:
    data: dict[str, Any] = {
        "opcode": block.opcode,
        "next": None,
        "parent": parent,
        "inputs": {},
        "fields": {
            name: _field_data(value) for name, value in block.fields.items()
        },
        "shadow": False,
        "topLevel": top_level,
    }
    if block.mutation is not None:
        data["mutation"] = dict(block.mutation)
    if top_level:
        data["x"], data["y"] = x or 0, y or 0
    blocks[block.block_id] = data
    if block.opcode == "procedures_definition" and block.mutation is not None:
        prototype = _Block(
            "procedures_prototype",
            mutation=dict(block.mutation),
            procedure_name=block.procedure_name,
        )
        _serialize_block(
            prototype, blocks, parent=block.block_id, top_level=False
        )
        blocks[prototype.block_id]["shadow"] = True
        data["inputs"]["custom_block"] = [1, prototype.block_id]
    previous_id: str | None = None
    for child in block.body:
        child_id = _serialize_block(
            child,
            blocks,
            parent=block.block_id if previous_id is None else previous_id,
            top_level=False,
        )
        if previous_id is None:
            if block.body_as_substack:
                data["inputs"]["SUBSTACK"] = [2, child_id]
            else:
                data["next"] = child_id
        else:
            blocks[previous_id]["next"] = child_id
        previous_id = child_id
    if block.else_body:
        previous_else: str | None = None
        for child in block.else_body:
            child_id = _serialize_block(
                child,
                blocks,
                parent=block.block_id if previous_else is None else previous_else,
                top_level=False,
            )
            if previous_else is None:
                data["inputs"]["SUBSTACK2"] = [2, child_id]
            else:
                blocks[previous_else]["next"] = child_id
            previous_else = child_id
    for name, input_value in block.inputs.items():
        if input_value.kind in ("substack", "substack_else"):
            if name not in data["inputs"]:
                data["inputs"][name] = [2, None]
            continue
        data["inputs"][name] = _serialize_input(
            input_value, blocks, block.block_id
        )
    if block.body_as_substack and block.body and "SUBSTACK" not in data["inputs"]:
        data["inputs"]["SUBSTACK"] = [2, None]
    return block.block_id


def _serialize_input(
    input_value: _Input,
    blocks: dict[str, dict[str, Any]],
    parent_id: str,
) -> list[Any]:
    value, kind = input_value.value, input_value.kind
    if kind == "menu":
        menu_block = _Block(
            input_value.menu_opcode or "",
            fields={input_value.menu_field or "OPTION": _menu_value(value)},
        )
        _serialize_block(
            menu_block, blocks, parent=parent_id, top_level=False
        )
        blocks[menu_block.block_id]["shadow"] = True
        return [1, menu_block.block_id]
    if isinstance(value, _Reporter):
        reporter = _Block(value.opcode, dict(value.inputs), dict(value.fields))
        _serialize_block(reporter, blocks, parent=parent_id, top_level=False)
        return [2, reporter.block_id]
    shadow_type, shadow_value = _shadow_value(value, kind)
    return [1, [shadow_type, shadow_value]]


def _field_data(value: Any) -> list[Any]:
    if isinstance(value, tuple) and len(value) == 2:
        return [str(value[0]), value[1]]
    return [str(_menu_value(value)), None]


def _menu_value(value: Any) -> Any:
    if isinstance(value, (Number, Text)):
        return value.value
    return value


def _shadow_value(value: Any, kind: str) -> tuple[int, str]:
    if isinstance(value, Number):
        return 4, str(value.value)
    if isinstance(value, Text):
        return 10, value.value
    if kind in ("text", "auto") and isinstance(value, str):
        return 10, value
    if kind == "boolean":
        raise TypeError("Boolean inputs must be reporter blocks")
    if kind in ("number", "integer", "positive", "angle") or isinstance(value, (int, float)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{kind} input requires a number or reporter")
        if not math.isfinite(value):
            raise ValueError("Numeric block inputs must be finite")
        if kind == "integer":
            return 6, str(value)
        if kind == "positive":
            return 5, str(value)
        if kind == "angle":
            return 8, str(value)
        return 4, str(value)
    if value is None:
        return 10, ""
    return 10, str(value)
