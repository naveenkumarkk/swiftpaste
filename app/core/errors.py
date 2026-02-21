from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class AppError(Exception):
    code: str
    message: str
    status_code: int = 400
    details: Optional[dict[str,Any]] = None