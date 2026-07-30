from fastapi import APIRouter

from .. import __version__
from ..schemas import HealthReport
from ..services.system_check import run_checks

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthReport)
def health() -> HealthReport:
    checks = run_checks()
    return HealthReport(ready=all(c.ok for c in checks), version=__version__, checks=checks)
