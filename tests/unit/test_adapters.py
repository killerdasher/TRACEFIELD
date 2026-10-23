"""Unit tests for the typed adapter boundary (Phase 5, decision D19).

The boundary must fail closed at construction AND at call time, keep
health claims factual, and never expose an execution path outside the
allowlisted local backends.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tracefield.adapters import (
    ADAPTERS,
    EXIFTOOL_META,
    INTEGRATED,
    SPEC_ONLY,
    AdapterError,
    AdapterSpec,
    describe,
    get_adapter,
    health,
    run_adapter,
)

pytestmark = pytest.mark.unit


class TestRegistry:
    def test_registry_ids_unique_and_stable(self) -> None:
        assert set(ADAPTERS) == {"exiftool-meta", "ffprobe-streams", "tesseract-ocr"}
        # Registry order is declaration order (dict preserves it) — no
        # discovery, no scanning, deterministic output.
        assert list(ADAPTERS) == ["exiftool-meta", "ffprobe-streams", "tesseract-ocr"]

    def test_every_backend_is_allowlisted(self) -> None:
        from tracefield.fieldtools.inspect import ALLOWED_BACKENDS

        for spec in ADAPTERS.values():
            assert spec.backend in ALLOWED_BACKENDS

    def test_get_adapter_unknown_is_honest_error(self) -> None:
        with pytest.raises(AdapterError) as exc:
            get_adapter("curl-scraper")
        assert "unknown adapter" in str(exc.value)
        assert "exiftool-meta" in str(exc.value)  # lists what IS registered

    def test_only_reference_adapter_claims_integrated(self) -> None:
        """No unverified bulk integrations: exactly one adapter may claim
        'integrated', and it must be the E2E-tested reference adapter."""
        integrated = [s.id for s in ADAPTERS.values() if s.integration_state == INTEGRATED]
        assert integrated == ["exiftool-meta"]
        assert EXIFTOOL_META.integration_state == INTEGRATED
        assert {s.id for s in ADAPTERS.values() if s.integration_state == SPEC_ONLY} == {
            "ffprobe-streams",
            "tesseract-ocr",
        }


class TestSpecConstruction:
    def test_non_allowlisted_backend_refused_at_construction(self) -> None:
        with pytest.raises(AdapterError) as exc:
            AdapterSpec(
                id="evil",
                display_name="Evil",
                backend="curl",
                version_argv=("curl", "--version"),
                run_argv=("curl", "{path}"),
                description="",
            )
        assert "non-allowlisted" in str(exc.value)

    def test_argv_must_come_from_own_backend(self) -> None:
        with pytest.raises(AdapterError):
            AdapterSpec(
                id="mismatch",
                display_name="Mismatch",
                backend="exiftool",
                version_argv=("ffprobe", "-version"),  # wrong binary
                run_argv=("exiftool", "{path}"),
                description="",
            )

    def test_run_argv_requires_path_placeholder(self) -> None:
        with pytest.raises(AdapterError) as exc:
            AdapterSpec(
                id="no-placeholder",
                display_name="NP",
                backend="exiftool",
                version_argv=("exiftool", "-ver"),
                run_argv=("exiftool", "-json"),  # no {path}
                description="",
            )
        assert "{path}" in str(exc.value)

    def test_unknown_integration_state_refused(self) -> None:
        with pytest.raises(AdapterError):
            AdapterSpec(
                id="bad-state",
                display_name="BS",
                backend="exiftool",
                version_argv=("exiftool", "-ver"),
                run_argv=("exiftool", "{path}"),
                description="",
                integration_state="healthy",  # forbidden vocabulary
            )

    def test_run_argv_uses_absolute_path(self, tmp_path: Path) -> None:
        """A relative path becomes absolute so it can never start with a
        dash and be misread as a backend option."""
        argv = EXIFTOOL_META.run_argv_for(tmp_path / "img.png")
        assert argv[-1] == str((tmp_path / "img.png").resolve())
        assert "--" in argv  # defense in depth for backends that support it

    def test_extra_args_inserted_before_path(self, tmp_path: Path) -> None:
        argv = EXIFTOOL_META.run_argv_for(tmp_path / "img.png", ("-a",))
        assert argv[-3:] == ["-a", "--", str((tmp_path / "img.png").resolve())]


class TestHealth:
    def test_health_vocabulary_is_factual(self) -> None:
        from tracefield.adapters import (
            HEALTH_BLOCKED,
            HEALTH_DISABLED,
            HEALTH_MISSING_BACKEND,
            HEALTH_READY,
        )

        allowed = {HEALTH_READY, HEALTH_MISSING_BACKEND, HEALTH_DISABLED, HEALTH_BLOCKED}
        # 'healthy' must NOT be a health state: we do not persist dated
        # health checks, so we never claim it.
        assert "healthy" not in allowed

    def test_ready_when_probe_answers(self, tf_home: Path) -> None:
        import shutil

        if shutil.which("exiftool") is None:
            pytest.skip("exiftool not installed; ready-state needs a real backend")
        h = health(EXIFTOOL_META)
        assert h["state"] == "ready"
        assert h["backend_version"]  # version captured from the probe
        assert h["checked_at"].endswith("Z")
        assert "version probe" in h["note"]

    def test_missing_backend_is_honest(
        self, tf_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("shutil.which", lambda exe: None)
        h = health(EXIFTOOL_META)
        assert h["state"] == "missing-backend"
        assert h["backend_version"] == ""

    def test_kill_switch_reports_disabled(
        self, tf_home: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TRACEFIELD_ADAPTERS", "0")
        h = health(EXIFTOOL_META)
        assert h["state"] == "disabled"


class TestDescribe:
    def test_describe_is_side_effect_free(self) -> None:
        d = describe(EXIFTOOL_META)
        assert d["id"] == "exiftool-meta"
        assert d["catalogue_id"] == "tool_001b8f8a85"  # linked, not duplicated
        assert d["license_id"] == "GPL-3.0"
        assert d["upstream_url"] == "https://exiftool.org/"
        assert d["needs_network"] is False
        assert "not exercised end-to-end" not in d["description"]  # integrated one


class TestRunRefusals:
    def test_missing_backend_raises_with_state(
        self, tf_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        f = tmp_path / "a.txt"
        f.write_text("x")
        monkeypatch.setattr("shutil.which", lambda exe: None)
        with pytest.raises(AdapterError) as exc:
            run_adapter(EXIFTOOL_META, f)
        assert exc.value.state == "missing-backend"

    def test_disabled_raises_with_state(
        self, tf_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        f = tmp_path / "a.txt"
        f.write_text("x")
        monkeypatch.setenv("TRACEFIELD_ADAPTERS", "0")
        with pytest.raises(AdapterError) as exc:
            run_adapter(EXIFTOOL_META, f)
        assert exc.value.state == "disabled"

    def test_non_file_input_refused(self, tf_home: Path, tmp_path: Path) -> None:
        with pytest.raises(AdapterError) as exc:
            run_adapter(EXIFTOOL_META, tmp_path / "missing.txt")
        assert "not a regular file" in str(exc.value)

    def test_call_time_allowlist_recheck_blocks_sabotaged_spec(
        self, tf_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even if construction-time validation were bypassed, run_adapter
        re-checks the allowlist before touching PATH."""
        f = tmp_path / "a.txt"
        f.write_text("x")
        import tracefield.adapters as adapters_mod

        monkeypatch.setattr(
            adapters_mod, "ALLOWED_BACKENDS", frozenset({"exiftool"}) - {"exiftool"}
        )
        with pytest.raises(AdapterError) as exc:
            run_adapter(EXIFTOOL_META, f)
        assert "not allowlisted" in str(exc.value)

    def test_network_spec_requires_double_opt_in(
        self, tf_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A future network adapter is refused without BOTH the env flag
        and the per-call opt-in — mirroring the fetch policy."""
        f = tmp_path / "a.txt"
        f.write_text("x")
        spec = AdapterSpec(
            id="net-probe",
            display_name="Net probe (synthetic)",
            backend="exiftool",  # allowlisted; the point is the network gate
            version_argv=("exiftool", "-ver"),
            run_argv=("exiftool", "{path}"),
            description="synthetic network adapter for the opt-in test",
            needs_network=True,
        )
        with pytest.raises(AdapterError) as exc:
            run_adapter(spec, f)  # no env flag, no opt-in
        assert exc.value.state == "blocked"
        monkeypatch.setenv("TRACEFIELD_ALLOW_NETWORK", "1")
        with pytest.raises(AdapterError) as exc:
            run_adapter(spec, f)  # env flag but no per-call opt-in
        assert exc.value.state == "blocked"
