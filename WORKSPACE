load("@bazel_tools//tools/build_defs/repo:http.bzl", "http_archive")

http_archive(
    name = "rules_oci",
    sha256 = "e96d70faa4bace3e09fdb1d7d1441b838920f491588889ff9a7e2615afca5799",
    strip_prefix = "rules_oci-2.0.0-alpha2",
    url = "https://github.com/bazel-contrib/rules_oci/releases/download/v2.0.0-alpha2/rules_oci-v2.0.0-alpha2.tar.gz",
)

load("@rules_oci//oci:dependencies.bzl", "rules_oci_dependencies")
rules_oci_dependencies()

load("@rules_oci//oci:repositories.bzl", "oci_register_toolchains")
oci_register_toolchains(name = "oci")

# Pull base image
load("@rules_oci//oci:pull.bzl", "oci_pull")

oci_pull(
    name = "vllm_base",
    registry = "index.docker.io",
    repository = "vllm/vllm-openai",
    tag = "latest",  # We'll use tag for now since we don't have a specific digest
    platforms = ["linux/amd64"],
)