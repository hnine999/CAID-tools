tasks.register<Exec>("build-docker") {
    inputs.files("Context/Dockerfile")
    inputs.dir("Context/app")
    inputs.dir("Context/fluxbox")
    inputs.files("build_novnc_docker.sh")

    commandLine = listOf("bash", "build_novnc_docker.sh")
}
