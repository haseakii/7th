class ScriptError(Exception):
    pass


class GameStuckError(Exception):
    pass


class GameBugError(Exception):
    pass


class RequestHumanTakeover(Exception):
    """脚本无法处理，需要人工介入（可能是配置错误）。"""
    pass
