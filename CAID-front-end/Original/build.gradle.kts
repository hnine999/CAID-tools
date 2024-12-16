val theiaDocker: String? by project

val DEPI_IMPL: String? by project
val GSN_ASSURANCE: String? by project
val WEBGME_DEPI: String? by project

val parameter_map = mapOf(
    "theiaDocker" to theiaDocker,
    "DEPI_IMPL" to DEPI_IMPL,
    "GSN_ASSURANCE" to GSN_ASSURANCE,
    "WEBGME_DEPI" to WEBGME_DEPI
)

tasks.register<Exec>("build-docker") {
    inputs.files("Context/Dockerfile")
    inputs.files("build_caid_front_end_docker.py")

    environment.putAll(parameter_map)
    commandLine = listOf("bash", "build_caid_front_end_docker.sh")
}
