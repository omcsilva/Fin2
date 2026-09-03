"""Stable contracts shared by institution-specific import adapters."""
from dataclasses import dataclass
from typing import Any,Iterable,Protocol


@dataclass(frozen=True)
class SourceRow:
    locator:dict[str,Any]
    values:dict[str,Any]


class Adapter(Protocol):
    adapter_id:str
    version:str
    document_type:str

    def detect(self,filename:str,body:bytes)->int: ...
    def parse(self,filename:str,body:bytes)->Iterable[SourceRow]: ...
    def normalize(self,row:SourceRow,db,options:dict[str,Any]|None=None)->dict[str,Any]: ...
