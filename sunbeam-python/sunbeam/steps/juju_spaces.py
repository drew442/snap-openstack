import json
import subprocess
from typing import Dict, Any, List

from sunbeam.core.common import BaseStep, Result, ResultType, Status
from sunbeam.core.questions import load_answers

NETWORK_ISOLATION_KEY = "network_isolation"

class EnsureJujuSpacesStep(BaseStep):
    """Ensure Juju spaces exist in the given model based on network_isolation answers."""

    def __init__(self, client, model: str):
        super().__init__(
            f"Ensure Juju spaces in model '{model}'",
            f"Creating/updating Juju spaces in model '{model}'",
        )
        self.client = client
        self.model = model

    def _answers(self) -> Dict[str, Any]:
        return load_answers(self.client, NETWORK_ISOLATION_KEY) or {}

    def is_skip(self, status: Status | None = None) -> Result:
        ni = self._answers().get("network_isolation") or {}
        if not ni.get("enable_isolation"):
            return Result(ResultType.SKIPPED, "Network isolation disabled")
        if not (ni.get("spaces") or {}):
            return Result(ResultType.SKIPPED, "No spaces specified")
        return Result(ResultType.COMPLETED)

    def _juju(self, *args: str) -> str:
        # Run juju in this environment; we must target a model explicitly.
        cmd = ["juju", *args, "--model", self.model]
        out = subprocess.run(
            cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True
        )
        return out.stdout

    def run(self, status: Status | None = None) -> Result:
        ni = self._answers().get("network_isolation") or {}
        spaces: Dict[str, Dict[str, Any]] = ni.get("spaces") or {}

        # Get existing spaces in model
        try:
            raw = self._juju("spaces", "--format", "json")
            existing = {s["name"] for s in json.loads(raw).get("spaces", [])}
        except Exception as e:
            return Result(ResultType.FAILED, f"Unable to read model spaces: {e}")

        # Create or reconcile each specified space
        for name, spec in spaces.items():
            subnets: List[str] = (spec or {}).get("subnets") or []
            if not subnets:
                continue
            try:
                if name in existing:
                    # Best-effort reconciliation
                    try:
                        self._juju("set-space-subnets", name, *subnets)
                    except Exception:
                        # Some controllers may not support; ignore
                        pass
                else:
                    self._juju("add-space", name, *subnets)
            except Exception as e:
                return Result(ResultType.FAILED, f"Failed to ensure space {name}: {e}")

        # Set default-space for the model (bindings still explicit elsewhere)
        try:
            subprocess.run(
                ["juju", "model-config", "--model", self.model, "default-space=management"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True,
            )
        except Exception:
            pass

        return Result(ResultType.COMPLETED)
