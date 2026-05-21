"""ALAS 风格异常定义"""


class RequestHumanTakeover(Exception):
    pass


class ScriptError(Exception):
    pass


class TaskEnd(Exception):
    pass


class GameNotRunningError(Exception):
    pass


class GameStuckError(Exception):
    pass


class GameTooManyClickError(Exception):
    pass


class GameBugError(Exception):
    pass


class GamePageUnknownError(Exception):
    pass


class EmulatorNotRunningError(Exception):
    pass
