@Library('jenkins-shared-library@devpi-function') _

def mainBranch = 'master'

standardBuild(
  version: 2,
  skipBranchBuilds: true,
  mainBranch: mainBranch,
  jobDescription: 'Uploads flask-peewee module to private devpi repository',
  properties: [buildDiscarder(logRotator(artifactDaysToKeepStr: '', artifactNumToKeepStr: '', daysToKeepStr: '', numToKeepStr: '10'))],
) { TAG, BRANCH_NAME, GIT_SHA ->

  // Upload flask-peewee to private devpi repository
  stage("Upload flask-peewee") {
    if (BRANCH_NAME == image.branch) {
      utils.uploadPyModule(path: ".")
    }
  }
}
