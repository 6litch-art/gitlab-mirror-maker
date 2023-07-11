install:
	poetry build
	pip install --force-reinstall dist/gitlab_mirror_maker*.whl

