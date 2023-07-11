import requests

# GitLab api address
api = 'https://gitlab.com/api/v4'

# GitLab user authentication token
token = ''

def get_repos(visibility = '', archive = False, page = 1):
    """Finds all public GitLab repositories of authenticated user.

    Returns:
     - List of public GitLab repositories.
    """

    gitlab_visibility = f"visibility={visibility}&" if visibility else ""
    gitlab_archived = "true" if archive else "false"

    url = api + f'/projects?{gitlab_visibility}owned=true&archived={gitlab_archived}&page={page}'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    nextRepos = []
    nextPage = r.headers["X-Next-Page"] if "X-Next-Page" in r.headers else 0
    if nextPage: nextRepos = get_repos(visibility, archive, nextPage)

    repos = r.json()
    for repo in nextRepos:
        repos.append(repo)

    return repos


def get_user():
    url = api+'/user'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()


def get_repo_by_shorthand(shorthand, visibility):

    projects = get_repos(visibility)

    project_id = -1
    for project in projects:
        project_id = project["id"] if project["path_with_namespace"] == shorthand else -1
        if (project_id > 0): break

    if (project_id < 0):
        print("Failed to find project with path: "+shorthand + " (is it private/internal repository? use `--gitlab-private`)")
        raise SystemExit(1)

    url = f'/projects/{project_id}'
    url = api+url
    headers = {'Authorization': f'Bearer {token}'}

    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()



def get_mirrors(gitlab_repo):
    """Finds all configured mirrors of GitLab repository.

    Args:
     - gitlab_repo: GitLab repository.

    Returns:
     - List of mirrors.
    """

    url = f'/projects/{gitlab_repo["id"]}/remote_mirrors'
    url = api + url
    headers = {'Authorization': f'Bearer {token}'}

    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    return r.json()


def mirror_target_exists(github_repos, mirrors):
    """Checks if any of the given mirrors points to any of the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - mirrors: List of mirrors configured for a single GitLab repository.

    Returns:
     - True if any of the mirror points to an existing GitHub repository, False otherwise.
    """

    for mirror in mirrors:
        if any(mirror['url'] and mirror['url'].endswith(f'{repo["full_name"]}.git') for repo in github_repos):
            return True

    return False


def create_mirror(gitlab_repo, github_token, github_org, github_user):
    """Creates a push mirror of GitLab repository.

    For more details see: 
    https://docs.gitlab.com/ee/user/project/repository/repository_mirroring.html#pushing-to-a-remote-repository-core

    Args:
     - gitlab_repo: GitLab repository to mirror.
     - github_token: GitHub authentication token.
     - github_user: GitHub username under whose namespace the mirror will be created (defaults to GitLab username if not provided).

    Returns:
     - JSON representation of created mirror.
    """

    url = f'/projects/{gitlab_repo["id"]}/remote_mirrors'
    url = api + url
    headers = {'Authorization': f'Bearer {token}'}

    github_path = f'{github_org}' if github_org else f'{github_user}' 
    data = {
        'url': f'https://{github_user}:{github_token}@github.com/{github_path}/{gitlab_repo["path_with_namespace"]}.git',
        'enabled': True
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Failed to mirror repository: "+url)
        raise SystemExit(e)

    return r.json()

def delete_mirrors(gitlab_repo):
    """Delete a remote mirror in GitLab repository.

    For more details see: 
    https://docs.gitlab.com/ee/api/remote_mirrors.html#delete-a-remote-mirror

    Args:
     - gitlab_repo: GitLab repository to mirror.

    """

    mirrors = get_mirrors(gitlab_repo)
    for mirror in mirrors:

        url = f'/projects/{gitlab_repo["id"]}/remote_mirrors/{mirror["id"]}'
        url = api + url
        headers = {'Authorization': f'Bearer {token}'}

        try:
            r = requests.delete(url, headers=headers)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print("Failed to mirror repository "+url)
            raise SystemExit(e)
