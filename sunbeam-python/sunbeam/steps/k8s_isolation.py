import json
import logging
from typing import Optional

from sunbeam.clusterd.client import Client
from sunbeam.core.common import BaseStep, Result, ResultType, Status
from sunbeam.core.k8s import (
    K8SHelper,
    K8SError,
)
from sunbeam.core.questions import load_answers
from sunbeam.core.openstack import OPENSTACK_MODEL
from .k8s import get_kube_client, KubeClientError  # reuse existing helpers

LOG = logging.getLogger(__name__)

# We’ll store the extra ranges under the same config bucket that k8s.py already uses.
K8S_ADDONS_CONFIG_KEY = "TerraformVarsK8SAddons"

# network isolation answers bucket, per our earlier plan/messages
NETWORK_ISOLATION_CONFIG_KEY = "network_isolation"

# Namespaces & names used by MetalLB CRDs
METALLB_NS = K8SHelper.get_loadbalancer_namespace()  # usually "metallb-system"
PUBLIC_POOL_NAME = "sunbeam-public-pool"
INTERNAL_POOL_NAME = "sunbeam-internal-pool"

# Traefik app names (match existing endpoint prompts in k8s.py)
TRAEFIK_APPS = {
    "traefik": INTERNAL_POOL_NAME,
    "traefik-public": PUBLIC_POOL_NAME,
    "traefik-rgw": PUBLIC_POOL_NAME,
}


class EnsureMetalLBIsolationStep(BaseStep):
    """Create MetalLB IPAddressPools + L2Advertisements and annotate Traefik services."""

    def __init__(self, client: Client, model: str = OPENSTACK_MODEL):
        super().__init__(
            "Ensure MetalLB pools and Traefik annotations",
            "Applying MetalLB pools and Traefik service annotations",
        )
        self.client = client
        self.model = model
        self.kube = None

    def _ranges_from_answers(self) -> tuple[Optional[str], Optional[str]]:
        """Return (public_range, internal_range)."""
        addons = load_answers(self.client, K8S_ADDONS_CONFIG_KEY).get("k8s-addons", {})
        ni = load_answers(self.client, NETWORK_ISOLATION_CONFIG_KEY)

        # Prefer explicit split ranges if present (we’ll add the prompts in §2 below)
        pub = addons.get("lb_public_pool")
        internal = addons.get("lb_internal_pool")

        # Fallback: if only a single range is set, use it for both
        single = addons.get("loadbalancer")
        if not pub and single:
            pub = single
        if not internal and single:
            internal = single

        # If user disabled isolation, we still succeed harmlessly (we’ll skip in is_skip)
        enable_iso = bool(ni.get("enable_isolation")) if isinstance(ni, dict) else False
        if not enable_iso:
            return (None, None)

        return (pub, internal)

    def _ensure_pool(self, name: str, cidrs_or_ranges: str) -> None:
        pool_res = K8SHelper.get_lightkube_loadbalancer_resource()
        body = pool_res(
            metadata={"name": name, "namespace": METALLB_NS},
            spec={"addresses": [r.strip() for r in cidrs_or_ranges.split(",") if r.strip()]},
        )
        try:
            # Create or replace
            self.kube.create(body)
        except Exception as e:
            # If exists, replace it (generic CRDs typically accept replace)
            try:
                self.kube.replace(pool_res, name=name, namespace=METALLB_NS, body=body)
            except Exception as re:
                raise K8SError(f"Failed to apply IPAddressPool {name}: {re}") from e

    def _ensure_l2adv(self, name: str, pools: list[str]) -> None:
        adv_res = K8SHelper.get_lightkube_l2_advertisement_resource()
        body = adv_res(
            metadata={"name": name, "namespace": METALLB_NS},
            spec={"ipAddressPools": pools},
        )
        try:
            self.kube.create(body)
        except Exception as e:
            try:
                self.kube.replace(adv_res, name=name, namespace=METALLB_NS, body=body)
            except Exception as re:
                raise K8SError(f"Failed to apply L2Advertisement {name}: {re}") from e

    def _annotate_traefik_services_via_juju(self) -> None:
        """
        Prefer using Juju charm config to set Service annotations so the charm
        keeps Services reconciled. We can do this with `juju config` safely
        through the existing helper.
        """
        from sunbeam.core.juju import JujuHelper, JujuController

        controller = JujuController.load(self.client)
        j = JujuHelper(controller)

        # Only annotate apps that actually exist
        existing = set(j.get_application_names(self.model))
        for app, pool in TRAEFIK_APPS.items():
            if app not in existing:
                continue

            # Build annotations payload for the charm
            ann = {
                K8SHelper.get_loadbalancer_address_pool_annotation(): pool
            }
            # NB: j.cli defaults to JSON mode; disable it for `juju config`.
            j.cli(
                "config",
                app,
                f'kubernetes-service-annotations={json.dumps(ann)}',
                json_format=False,
            )

    def is_skip(self, status: Status | None = None) -> Result:
        try:
            self.kube = get_kube_client(self.client)
        except KubeClientError as e:
            return Result(ResultType.FAILED, str(e))

        public_range, internal_range = self._ranges_from_answers()
        if not public_range and not internal_range:
            # Isolation not enabled or no ranges provided
            return Result(ResultType.SKIPPED)

        return Result(ResultType.COMPLETED)

    def run(self, status: Status | None = None) -> Result:
        try:
            public_range, internal_range = self._ranges_from_answers()
            if public_range:
                self._ensure_pool(PUBLIC_POOL_NAME, public_range)
                self._ensure_l2adv("sunbeam-public-adv", [PUBLIC_POOL_NAME])

            if internal_range:
                self._ensure_pool(INTERNAL_POOL_NAME, internal_range)
                self._ensure_l2adv("sunbeam-internal-adv", [INTERNAL_POOL_NAME])

            self._annotate_traefik_services_via_juju()

        except Exception as e:
            LOG.debug("MetalLB isolation step failed", exc_info=True)
            return Result(ResultType.FAILED, str(e))

        return Result(ResultType.COMPLETED)
