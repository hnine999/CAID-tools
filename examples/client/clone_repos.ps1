# Place and run this script in a folder to where you would like to clone the repositories.
# Modify $DEPI_HOST and $USERNAME as needed
$DEPI_HOST = 'localhost'
$USERNAME = 'demo'

$repos = @("eval-results", "eval-scripts", "gsn", "src", "test-runs", "testdata")

foreach ($repo_name in $repos) {
    git clone "http://$($DEPI_HOST):3000/$($USERNAME)/$($repo_name).git"
}
