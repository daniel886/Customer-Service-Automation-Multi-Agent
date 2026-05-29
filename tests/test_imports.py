"""Smoke import every module that doesn't require heavy 3rd-party deps."""
import importlib

import pytest


LIGHT_MODULES = [
    "core.config",
    "core.logger",
    "core.memory",
    "models.database",
    "models.schemas",
    "models",
    "tools.order_lookup",
    "tools.ticket",
    "tools",  # lazy
    "workflows.router",
    "workflows",  # lazy
    "scheduler.daily_report",
    "scheduler",
    "api.auth",
    "agents.consultation_agent",
    "agents.complaint_agent",
    "agents.tech_support_agent",
    "agents.aftersales_agent",
    "agents.base",
    "integrations.email_handler",
]


@pytest.mark.parametrize("mod", LIGHT_MODULES)
def test_import(mod):
    importlib.import_module(mod)
