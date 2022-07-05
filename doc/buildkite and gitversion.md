# How to call gitversion in a buildkite pipeline

<p style="float: right">Jonathan Newnham, 2022-07-05</p>

This file explains how to run [GitVersion](https://gitversion.net/docs/learn/why) in [buildkite](https://buildkite.com) build and CI pipelines so that developers can just commit using `feat:` or `fix:` or `chore:` and not have to worry about updating versions in build files and changelogs manually.

## Add a configuration file for GitVersion

The first step is to add a `GitVersion.yml` configuration file to the root of your
repository:

```yaml
# set up for https://www.conventionalcommits.org/en/v1.0.0/

mode: MainLine
major-version-bump-message: "^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\\([\\w\\s-]*\\))?(!:|:.*\\n\\n((.+\\n)+\\n)?BREAKING\\sCHANGE:\\s.+)"
minor-version-bump-message: "^(feat)(\\([\\w\\s-]*\\))?:"
patch-version-bump-message: "^(build|chore|ci|docs|fix|perf|refactor|revert|style|test)(\\([\\w\\s-]*\\))?:"
```

## Add GitVersion to docker-compose

The second step is to set up docker to be able to run gitversion in
`docker-compose.yml`:

```yaml
services:
    gitversion:
        image: gittools/gitversion
        command: /repo -output file -outputfile version.json
        volumes:
            - .:/repo
        working_dir: /repo
        environment:
            - BUILDKITE
            - BUILDKITE_BRANCH
            - BUILDKITE_PULL_REQUEST
```

## Update your build to call GitVersion and use the result

The third and final step is to update your build scripts to run gitversion and
use the result:

```sh
# run gitversion, producing `version.json`:
docker-compose run --rm gitversion
# extract the version string from `version.json`:
export APP_VERSION=$(cat version.json | jq -j '.SemVer')

# depending on your language, set or use the version in the build
docker-compose run --rm maven mvn versions:set -DnewVersion="$APP_VERSION" -f pom.xml
docker-compose run --rm python python setup.py --version="$APP_VERSION"
docker-compose run --rm npm version "$APP_VERSION"
docker-compose run --rm rust cargo set-version --allow-dirty "$APP_VERSION"

# after (and only after) the build is succeeds and is deployed/uploaded, tag the repository so that the next version check can use it:
git tag $APP_VERSION
git push origin $APP_VERSION
```

## Notes

1. I tried using the docker plugin in the buildkite pipeline; that's tricky
   because it's hard to get the result out of the container and save it for use
   in the actual build step.
2. If you're doing this in a makefile, be careful of parallelism and seperate
   shells meaning variables don't stay set between lines
3. If you have multiple apps in the one repository, GitVersion is probably not for you because it relies on (repository-wide) Git tags.
4. Instead of running the GitVersion docker image, you could add the GitVersion binary to your buildkite build image and call it directly. That's more complicated so I haven't tried it.
5. If you don't push a tag after the build succeeds, gitversion will gradually get slower and will not work correctly. For example, multiple `feat` commits will only cause one minor version bump.
6. If you tag without checking for a successful build, you may get more version bumps than you want; that usually isn't the end of the world though
7. The "conventional commits" thing makes it straightforward to generate a changelog from your git history but I haven't figured out how to automate that yet.