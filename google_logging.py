import json
from enum import Enum

class LogSeverity(str, Enum):
    DEFAULT = 'DEFAULT'
    DEBUG = 'DEBUG'
    INFO = 'INFO'
    NOTICE = 'NOTICE'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'
    ALERT = 'ALERT'
    EMERGENCY = 'EMERGENCY'


def structured_log(
        message: str, 
        severity: LogSeverity = LogSeverity.NOTICE
    ):
    entry = dict(severity=severity, message=message)
    print(json.dumps(entry))

if __name__ == '__main__':
    structured_log('hello world')