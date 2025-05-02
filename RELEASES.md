# Release process

Only tags are used by now (not releases).

# Tagging a release

If a version needs to be changed, edit `sim800l/__version__.py`.

This file is read by *setup.py*.

If the version is not changed, the publishing procedure works using the same version with a different build number.

The GITHUB_RUN_NUMBER environment variable, when available, is read by *setup.py*.

Push all changes:

```shell
git commit -a
git push
```

_After pushing the last commit_, add a local tag (shall be added AFTER the commit that needs to be published):

```shell
git tag # list local tags
git tag v0.1.4
```

Notes:

- correspondence between tag and `__version__.py` is not automatic.
- the tag must start with "v" if a GitHub Action workflow needs to be run

Push this tag to the origin, which starts the PyPI publishing workflow (GitHub Action):

```shell
git push origin v0.1.4
git ls-remote --tags https://github.com/Ircama/sim800l-gsm-module # list remote tags
```

Check the published tag here: https://github.com/Ircama/sim800l-gsm-module/tags

It shall be even with the last commit.

Check the GitHub Action: https://github.com/Ircama/sim800l-gsm-module/actions

Check PyPI:

- https://test.pypi.org/manage/project/sim800l-gsm-module/releases/
- https://pypi.org/manage/project/sim800l-gsm-module/releases/

End user publishing page:

- https://test.pypi.org/project/sim800l-gsm-module/
- https://pypi.org/project/sim800l-gsm-module/

Verify whether wrong builds need to be removed.

Test installation:

```shell
cd
python3 -m pip uninstall -y sim800l-gsm-module
python3 -m pip install sim800l-gsm-module
python3
from sim800l import SIM800L
quit()
python3 -m pip uninstall -y sim800l-gsm-module
```

# Updating the same tag (using a different build number for publishing)

```shell
git tag # list tags
git tag -d v1.0.0 # remove local tag
git push --delete origin v1.0.0 # remove remote tag
git ls-remote --tags https://github.com/Ircama/sim800l-gsm-module # list remote tags
```

Then follow the tagging procedure again to add the tag to the latest commit.

# Testing the build procedure locally

```shell
cd <repository directory>
```

## Local build (using build):

```shell
python3 -m build --sdist --wheel --outdir dist/ .
python3 -m twine upload --repository testpypi dist/*
```

(change *testpypi*)

## Local build (using setup):

```shell
python3 setup.py sdist bdist_wheel
python3 -m twine upload --repository testpypi dist/*
```

(change *testpypi*)

## Local build (using build versions):

```shell
GITHUB_RUN_NUMBER=31 python3 setup.py sdist bdist_wheel
python3 -m twine upload --repository testpypi dist/*
```

(change *testpypi*)

## Removing directories

```shell
ls -l dist
rm -r build dist sim800l_gsm_module.egg-info
```

# Check version data

- https://pypi.org/pypi/sim800l-gsm-module/json
- https://test.pypi.org/pypi/sim800l-gsm-module/json
