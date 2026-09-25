# Model gateway runtime image

This image is the provider-free producer for the protected model-gateway sidecar. It contains the Python environment resolved by the repository's `uv.lock` and the pinned Alpine `aws` CLI required by the DynamoDB spend controller. It contains no API key, AWS credential, gateway policy, run capability, or case data.

Build it from the repository root. The digest-pinned base images and `--pull=false` make the command fail closed when the declared inputs are not available in the local builder cache.

```bash
docker build --pull=false -f infra/model-gateway-runtime/Containerfile -t lfb-model-gateway:paid .
docker image inspect lfb-model-gateway:paid --format '{{.Id}} {{json .RepoDigests}}'
```

The image is only a runtime producer. The outer harness still has to start the gateway with its per-run policy, capability, provider key, and protected spend controller, and it must place the sidecar on the run's isolated network. The image itself does not enforce network egress or credential delivery. The gateway launch path must also preserve access to the installed `legalforecast.evals` and spend-control modules when it stages the gateway package; a staged top-level `legalforecast` package that shadows the installed package will not provide that import closure.

The protected workflow supplies AWS OIDC credentials and the provider key at runtime. The image build and the optional smoke probe below use neither credential and make no AWS or provider call. A built-image smoke probe can be run with network disabled:

```bash
export LEGALFORECAST_MODEL_GATEWAY_RUNTIME_IMAGE="$(docker image inspect --format '{{.Id}}' lfb-model-gateway:paid)"
uv run pytest -q tests/test_model_gateway_runtime_image.py
```

The test checks the producer statically. If `LEGALFORECAST_MODEL_GATEWAY_RUNTIME_IMAGE` is set, it additionally checks the built image's Python import closure and `aws --version` through `docker run --network none`; it never invokes an AWS operation or a model endpoint.
