# SPDX-FileCopyrightText: 2026 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""LVM SAN storage backend implementation."""

from typing import Annotated

from pydantic import Field

from sunbeam.core.manifest import StorageBackendConfig
from sunbeam.storage.base import StorageBackendBase


class LVMSANConfig(StorageBackendConfig):
    """Configuration model for the LVM SAN storage backend."""

    target_helper: Annotated[
        str | None,
        Field(description="Cinder target helper to use for iSCSI exports"),
    ] = None


class LVMSANBackend(StorageBackendBase):
    """LVM SAN storage backend implementation."""

    backend_type = "lvm-san"
    display_name = "LVM SAN"
    generally_available = True

    @property
    def charm_name(self) -> str:
        """Return the charm name for this backend."""
        return "cinder-volume-lvm-san"

    @property
    def charm_channel(self) -> str:
        """Return the charm channel for this backend."""
        return "latest/edge"

    @property
    def charm_revision(self) -> str | None:
        """Return the charm revision for this backend."""
        return None

    @property
    def charm_base(self) -> str:
        """Return the charm base for this backend."""
        return "ubuntu@24.04"

    @property
    def supports_ha(self) -> bool:
        """Return whether this backend supports HA deployments."""
        return True

    def config_type(self) -> type[StorageBackendConfig]:
        """Return the configuration class for LVM SAN backend."""
        return LVMSANConfig
