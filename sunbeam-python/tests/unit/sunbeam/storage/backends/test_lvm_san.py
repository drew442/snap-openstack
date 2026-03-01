# SPDX-FileCopyrightText: 2026 - Canonical Ltd
# SPDX-License-Identifier: Apache-2.0

"""Tests for LVM SAN backend."""

import pytest

from tests.unit.sunbeam.storage.backends.test_common import BaseBackendTests


class TestLVMSANBackend(BaseBackendTests):
    """Tests for LVM SAN backend."""

    @pytest.fixture
    def backend(self, lvmsan_backend):
        """Provide LVM SAN backend instance."""
        return lvmsan_backend

    def test_backend_type_is_lvm_san(self, backend):
        """Test that backend type is 'lvm-san'."""
        assert backend.backend_type == "lvm-san"

    def test_display_name_mentions_lvm_san(self, backend):
        """Test that display name mentions LVM SAN."""
        assert "lvm san" in backend.display_name.lower()

    def test_charm_name_is_lvm_san_charm(self, backend):
        """Test that charm name is cinder-volume-lvm-san."""
        assert backend.charm_name == "cinder-volume-lvm-san"

    def test_supports_ha(self, backend):
        """Test that backend deploys on HA cinder-volume principal."""
        assert backend.supports_ha is True
        assert backend.principal_application == "cinder-volume"

    def test_config_optional_fields_work(self, backend):
        """Test that optional fields can be omitted."""
        config_class = backend.config_type()
        config = config_class.model_validate({})
        assert config.target_helper is None
        assert config.backend_availability_zone is None

    def test_target_helper_field_exists(self, backend):
        """Test that target helper can be configured."""
        config_class = backend.config_type()
        assert "target_helper" in config_class.model_fields

    def test_target_helper_value_validates(self, backend):
        """Test that target-helper is accepted."""
        config_class = backend.config_type()
        config = config_class.model_validate({"target-helper": "lioadm"})
        assert config.target_helper == "lioadm"
