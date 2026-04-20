"""System related API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Request

from ....config.constants import REGION_DEFAULT_TICKERS
from ....config.manager import get_config_manager
from ....utils.i18n_utils import detect_user_region_async
from ...config.settings import get_settings
from ..schemas import (
    AppInfoData,
    ConfigHealthData,
    ConfigHealthIssueData,
    HealthCheckData,
    SuccessResponse,
)


def _get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request, considering reverse proxy headers."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    if request.client:
        return request.client.host

    return None


def create_system_router() -> APIRouter:
    """Create system related routes."""
    router = APIRouter(prefix="/system", tags=["System"])
    settings = get_settings()

    @router.get(
        "/info",
        response_model=SuccessResponse[AppInfoData],
        summary="Get application info",
        description="Get ValueCell application basic information including name, version and environment",
    )
    async def get_app_info():
        """Get application basic information."""
        app_info = AppInfoData(
            name=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.APP_ENVIRONMENT,
        )
        return SuccessResponse.create(
            data=app_info, msg="Application info retrieved successfully"
        )

    @router.get(
        "/health",
        response_model=SuccessResponse[HealthCheckData],
        summary="Health check",
        description="Check service running status and version information",
    )
    async def health_check():
        """Service health status check."""
        health_data = HealthCheckData(
            status="healthy", version=settings.APP_VERSION, timestamp=datetime.now()
        )
        return SuccessResponse.create(
            data=health_data, msg="Service is running normally"
        )

    @router.get(
        "/config-health",
        response_model=SuccessResponse[ConfigHealthData],
        summary="Configuration health check",
        description="Summarize configuration issues that can affect runtime startup or provider availability",
    )
    async def get_config_health():
        """Get high-level configuration health summary."""
        report = get_config_manager().get_config_health()
        return SuccessResponse.create(
            data=ConfigHealthData(
                status=report.status,
                primary_provider=report.primary_provider,
                enabled_providers=report.enabled_providers,
                issues=[
                    ConfigHealthIssueData(
                        level=issue.level,
                        scope=issue.scope,
                        message=issue.message,
                    )
                    for issue in report.issues
                ],
            ),
            msg="Configuration health retrieved successfully",
        )

    @router.get(
        "/default-tickers",
        response_model=SuccessResponse[dict],
        summary="Get default tickers for homepage",
        description="Get region-aware default tickers based on user's IP location",
    )
    async def get_default_tickers(
        request: Request,
        region: Optional[str] = None,
    ):
        """Get default tickers for homepage based on user region.

        Returns region-appropriate stock tickers that the user can access.
        For China mainland users, returns A-share indices (accessible via akshare/baostock).
        For other regions, returns globally accessible indices.

        Args:
            request: FastAPI request object for extracting client IP.
            region: Optional region override for testing (cn or default).
        """
        if region and region in REGION_DEFAULT_TICKERS:
            detected_region = region
        else:
            client_ip = _get_client_ip(request)
            detected_region = await detect_user_region_async(client_ip)

        tickers = REGION_DEFAULT_TICKERS.get(
            detected_region, REGION_DEFAULT_TICKERS["default"]
        )

        return SuccessResponse.create(
            data={
                "region": detected_region,
                "tickers": tickers,
            },
            msg="Default tickers retrieved successfully",
        )

    return router
