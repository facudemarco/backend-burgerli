from typing import Annotated, Dict, List
from pydantic import BaseModel, Field, StringConstraints

TimeHHMM = Annotated[str, StringConstraints(pattern=r"^\d{2}:\d{2}$")]

class TimeRange(BaseModel):
    apertura: TimeHHMM
    cierre: TimeHHMM

class OpeningHoursPayload(BaseModel):
    opening_hours: Dict[str, List[TimeRange]] = Field(..., description="0..6 -> [{apertura,cierre}]")
