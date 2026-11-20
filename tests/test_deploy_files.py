"""The deploy files read as text, no Docker and no Bitbucket: bitbucket-pipelines.yml (the copy that builds and deploys
staging and production from cip-stg) and deploy/ask-model-download.py (run by deploy/Dockerfile). Written 15 Nov 2026
after production built one tag and pushed another, so it never deployed, and an image could ship without Ask's model."""
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_each_deploy_pushes_what_it_built_checks_it_first_and_waits_for_it_live():
    branches = yaml.safe_load((ROOT / "bitbucket-pipelines.yml").read_text())["pipelines"]["branches"]
    for branch, place in (("stg-deploy", "stg"), ("pro-deploy", "pro")):
        (group, last) = branches[branch]
        # the tests beside the build, fail-fast, and the deploy only after both (20 Nov 2026: nothing ran the tests)
        tests, image = (s["step"] for s in group["parallel"]["steps"])
        assert group["parallel"]["fail-fast"] and any("pytest" in line for line in tests["script"]), branch
        build, deploy = image["script"], last["step"]["script"]
        assert any(line.startswith("docker pull") and f":{place}-latest" in line for line in build), branch   # the cache to reuse
        built = re.findall(r'-t "([^"]+)"', next(line for line in build if line.startswith("docker build")))
        pushed = [line.split('"')[1] for line in build if line.startswith("docker push")]
        assert sorted(built) == sorted(pushed) and any(tag.endswith(f":{place}-latest") for tag in pushed), branch

        named = [line for line in build if "IMAGE_NAME=" in line]
        assert named == [line for line in deploy if "IMAGE_NAME=" in line], branch   # the deploy sets the image it pushed
        assert f":{place}-" in named[0] and "date" not in named[0], branch   # no clock: one name across 00:00 UTC

        first_push = next(i for i, line in enumerate(build) if line.startswith("docker push"))
        assert any("model_optimized.onnx" in line and "/healthz" in line for line in build[:first_push]), branch
        switch = next(i for i, line in enumerate(deploy) if "webapp config container set" in line)
        waits = [line for line in deploy[switch:] if "$BUILD" in line]   # data files in, not just up: /readyz, never /healthz
        assert waits and all("/readyz" in line and "/healthz" not in line for line in waits), branch


def test_the_image_build_stops_when_the_search_model_does_not_download(tmp_path):
    """Every download refused (a proxy on a port nobody listens on): the script must fail, so docker build stops
    rather than ship an image whose Ask quietly searches by words alone."""
    refused = {**os.environ, "https_proxy": "http://127.0.0.1:9", "HTTPS_PROXY": "http://127.0.0.1:9", "no_proxy": "", "NO_PROXY": ""}
    done = subprocess.run([sys.executable, str(ROOT / "deploy/ask-model-download.py"), str(tmp_path)],
                          env=refused, capture_output=True, text=True, timeout=60)
    assert done.returncode != 0 and "not downloaded" in done.stderr
    assert not (tmp_path / "model_optimized.onnx").exists()
