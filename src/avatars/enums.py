# src/avatars/enums.py
from enum import Enum

class OutputFormatEnum(str, Enum):
    SHORT = "short"
    NORMAL = "normal"
    LONG = "long"
    
class VoiceKeyEnum(str, Enum):
    US_FEMALE = "us_female"
    US_MALE = "us_male"
    UK_MALE = "uk_male"
    UK_FEMALE = "uk_female"