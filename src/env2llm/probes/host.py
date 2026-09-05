"""Host environment probe — cron, HTTP ports, tooling, examples test report."""

from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from env2llm.ir import HostEndpointIR, HostProbeIR

from .host_agents import collect_agents
from .host_collectors import (
    collect_containers,
    collect_ports,
    collect_processes,
    load_examples_summary,
    tail_log,
)
from .host_cron import _parse_cron_line, cron_entries_to_schedules, cron_probe_state
from .host_runtime import (
    AGENT_HTTP_ALWAYS_CHECK,
    DEFAULT_MONITOR_LOG,
    host_cli_capabilities,
    http_ok,
)

__all__ = [
    "_parse_cron_line",
    "collect_host_probe",
    "cron_entries_to_schedules",
]


def _probe_agent_http_endpoints() -> list[HostEndpointIR]:
    endpoints: list[HostEndpointIR] = []
    for port in range(8101, 8131):
        url = f"http://localhost:{port}/health"
        ok, detail = http_ok(url, timeout=1.5)
        if ok or port in AGENT_HTTP_ALWAYS_CHECK:
            endpoints.append(
                HostEndpointIR(
                    id=f"agent_http_{port}",
                    url=url,
                    ok=ok,
                    detail=detail if not ok else "healthy",
                )
            )
    return endpoints


def _probe_www_endpoints() -> tuple[list[HostEndpointIR], bool, bool]:
    www_ok, www_detail = http_ok("http://localhost:8788/www/", timeout=3.0)
    api_ok, api_detail = http_ok("http://localhost:8788/health", timeout=2.0)
    return (
        [
            HostEndpointIR(
                id="www_8788",
                url="http://localhost:8788/www/",
                ok=www_ok,
                detail=www_detail if not www_ok else "ok",
            ),
            HostEndpointIR(
                id="www_health",
                url="http://localhost:8788/health",
                ok=api_ok,
                detail=api_detail if not api_ok else "ok",
            ),
        ],
        www_ok,
        api_ok,
    )


def _host_probe_summaries(
    *,
    endpoints: list[HostEndpointIR],
    containers: list,
    processes: list,
    ports: list,
    agents: list,
    cron_ok: bool,
    www_ok: bool,
    api_ok: bool,
) -> dict[str, Any]:
    return {
        "crontab": cron_ok,
        "agent_http_any": any(ep.ok and ep.id.startswith("agent_http_") for ep in endpoints),
        "agent_http_8101": next(
            (ep.ok for ep in endpoints if ep.id == "agent_http_8101"),
            False,
        ),
        "www_8788": www_ok,
        "www_health": api_ok,
        "docker_containers": bool(containers),
        "processes": bool(processes),
        "ports": bool(ports),
        "agents": bool(agents),
    }


def _host_capabilities(
    *,
    endpoints: list[HostEndpointIR],
    containers: list,
    processes: list,
    ports: list,
    agents: list,
    cron_ok: bool,
    www_ok: bool,
    api_ok: bool,
) -> dict[str, Any]:
    return {
        **host_cli_capabilities(),
        **_host_probe_summaries(
            endpoints=endpoints,
            containers=containers,
            processes=processes,
            ports=ports,
            agents=agents,
            cron_ok=cron_ok,
            www_ok=www_ok,
            api_ok=api_ok,
        ),
    }


def _host_probe_status(capabilities: dict[str, Any]) -> str:
    available_count = sum(1 for value in capabilities.values() if value)
    if available_count >= 4:
        return "available"
    if available_count > 0:
        return "partial"
    return "unknown"


def _resolve_monitor_log(project_dir: Path) -> Path:
    monitor_log = Path(DEFAULT_MONITOR_LOG)
    if monitor_log.is_file():
        return monitor_log
    alt = project_dir / "output" / "monitoring" / "www-monitor.log"
    return alt if alt.is_file() else monitor_log


def collect_host_probe(*, project_dir: Path | str | None = None) -> HostProbeIR:
    """Snapshot cron, local services, and example-test readiness on this host."""
    root = Path(project_dir).resolve() if project_dir is not None else Path.cwd()
    now = datetime.now(timezone.utc).isoformat()

    cron_ok, cron_entries, taskinity_cron = cron_probe_state()
    endpoints = _probe_agent_http_endpoints()
    www_endpoints, www_ok, api_ok = _probe_www_endpoints()
    endpoints.extend(www_endpoints)

    ports = collect_ports()
    processes = collect_processes()
    containers = collect_containers()
    agents = collect_agents(root)
    capabilities = _host_capabilities(
        endpoints=endpoints,
        containers=containers,
        processes=processes,
        ports=ports,
        agents=agents,
        cron_ok=cron_ok,
        www_ok=www_ok,
        api_ok=api_ok,
    )

    report_path, examples_summary = load_examples_summary(root)
    monitor_log = _resolve_monitor_log(root)
    status = _host_probe_status(capabilities)

    return HostProbeIR(
        hostname=platform.node(),
        platform=platform.platform(),
        probed_at=now,
        status=status,  # type: ignore[arg-type]
        cron_available=cron_ok,
        cron_taskinity_installed=taskinity_cron,
        cron_entries=cron_entries,
        endpoints=endpoints,
        capabilities=capabilities,
        monitor_log_path=str(monitor_log) if monitor_log.is_file() else "",
        monitor_log_tail=tail_log(monitor_log),
        examples_report_path=report_path,
        examples_test_summary=examples_summary,
        ports=ports,
        processes=processes,
        containers=containers,
        agents=agents,
    )
