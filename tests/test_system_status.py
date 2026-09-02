import os
import signal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from personal_music_bot import system_status as system_status_module
from personal_music_bot.system_status import (
    ProcessMetrics,
    deployment_version,
    format_memory,
    status_embed,
)


def test_deployment_version_prefers_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    version_file = tmp_path / ".deploy-version"
    version_file.write_text("v0.1.0-prod.3\n", encoding="utf-8")
    monkeypatch.setenv("DEPLOY_VERSION", "v0.2.0-prod.4")

    assert deployment_version(version_file) == "v0.2.0-prod.4"


def test_deployment_version_reads_generated_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DEPLOY_VERSION", raising=False)
    version_file = tmp_path / ".deploy-version"
    version_file.write_text("v0.1.0-prod.7\n", encoding="utf-8")

    assert deployment_version(version_file) == "v0.1.0-prod.7"


def test_status_embed_contains_process_metrics() -> None:
    metrics = ProcessMetrics(
        cpu_percent=12.34,
        memory_bytes=128 * 1024**2,
        memory_percent=3.21,
    )

    embed = status_embed("v0.1.0-prod.8", metrics)
    fields = {field.name: field.value for field in embed.fields}

    assert fields["Version"] == "`v0.1.0-prod.8`"
    assert fields["CPU"] == "12.3%"
    assert fields["Memoria"] == "128.0 MiB (3.2%)"
    assert format_memory(10 * 1024**2) == "10.0 MiB"


@pytest.mark.asyncio
async def test_terminate_for_restart_signals_the_current_process(monkeypatch) -> None:
    sleep = AsyncMock()
    kill = MagicMock()
    monkeypatch.setattr(system_status_module.asyncio, "sleep", sleep)
    monkeypatch.setattr(system_status_module.os, "kill", kill)

    await system_status_module.terminate_for_restart()

    sleep.assert_awaited_once_with(system_status_module.RESTART_DELAY_SECONDS)
    kill.assert_called_once_with(os.getpid(), signal.SIGTERM)


def test_restart_command_is_restricted_to_administrators() -> None:
    assert system_status_module.SystemStatus.restart.guild_only is True
    assert system_status_module.SystemStatus.restart.default_permissions is not None
    assert system_status_module.SystemStatus.restart.default_permissions.administrator is True
