import requests
import sys
from pprint import pprint

# GitHub user authentication token
token = ''

# GitHub username (under this user namespace the mirrors will be created)
user = ''


def get_repos(github_org):
    """Finds all public GitHub repositories (which are not forks) of authenticated user.

    Returns:
     - List of public GitHub repositories.
    """

    github_path = f'orgs/{github_org}' if github_org else f'user' 
    url = f'https://api.github.com/{github_path}/repos'
    headers = {'Authorization': f'Bearer {token}'}

    repos = []
    try:
        while url:
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            repos.extend(r.json())
            # handle pagination
            url = r.links.get("next", {}).get("url", None)
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    # Return only non forked repositories
    return [x for x in repos if not x['fork']]


def repo_exists(github_repos, repo_slug):
    """Checks if a repository with a given slug exists among the public GitHub repositories.

    Args:
     - github_repos: List of GitHub repositories.
     - repo_slug: Repository slug (usually in a form of path with a namespace, eg: "username/reponame").

    Returns:
     - True if repository exists, False otherwise.
    """

    return any(repo['full_name'] == repo_slug for repo in github_repos)


def create_repo(gitlab_repo, github_org):
    """Creates GitHub repository based on a metadata from given GitLab repository.

    Args:
     - gitlab_repo: GitLab repository which metadata (ie. name, description etc.) is used to create the GitHub repo.

    Returns:
     - JSON representation of created GitHub repo.
    """

    github_name = gitlab_repo['path_with_namespace'].replace("/", "-")
    github_path = f'orgs/{github_org}' if github_org else f'user' 
    github_archive = gitlab_repo["archived"]
    github_type = False if gitlab_repo["visibility"] == "public" else True

    url = f'https://api.github.com/{github_path}/repos'
    headers = {'Authorization': f'Bearer {token}'}

    data = {
        'name': github_name,
        'description': f'[MIRROR] {gitlab_repo["description"]}',
        'homepage': gitlab_repo['web_url'],
        'private': github_type,
        'archived': github_archive,
        'has_wiki': False,
        'has_projects': False
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        if not "errors" in e.response.json() or e.response.json()["errors"][0]["message"] != "name already exists on this account":
            print("Failed to create github repository: "+gitlab_repo['path_with_namespace'])
            pprint(e.response.json(), stream=sys.stderr)
            raise SystemExit(e)

    return r.json()

def delete_repo(gitlab_repo, github_org):
    """Creates GitHub repository based on a metadata from given GitLab repository.

    Args:
     - gitlab_repo: GitLab repository which metadata (ie. name, description etc.) is used to create the GitHub repo.

    Returns:
     - JSON representation of created GitHub repo.
    """

    github_name = gitlab_repo['path_with_namespace'].replace("/", "-")
    github_path = f'{github_org}' if github_org else f'user' 
    github_archive = gitlab_repo["archived"]
    github_type = False if gitlab_repo["visibility"] == "public" else True

    url = f'https://api.github.com/repos/{github_path}/{github_name}'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        r = requests.delete(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        if not "message" in e.response.json() or e.response.json()["message"] != "Not Found":
            print("Failed to delete github repository: "+gitlab_repo['path_with_namespace'])
            pprint(e.response.json(), stream=sys.stderr)
            raise SystemExit(e)

def patch_repo(gitlab_repo, github_org):
    """Patches GitHub repository based on a metadata from given GitLab repository.

    Args:
     - gitlab_repo: GitLab repository which metadata (ie. name, description etc.) is used to create the GitHub repo.
     - github_org: GitHub organization name

    Returns:
     - JSON representation of created GitHub repo.
    """

    github_archive = gitlab_repo["archived"]
    github_type = False if gitlab_repo["visibility"] == "public" else True
    
    github_name = gitlab_repo['path_with_namespace'].replace("/", "-")
    github_path = f'{github_org}' if github_org else f'user' 
    headers = {'Authorization': f'Bearer {token}'}

    data = {
        'name': github_name,
        'description': f'[MIRROR] {gitlab_repo["description"]}',
        'homepage': gitlab_repo['web_url'],
        'private': github_type,
        'has_wiki': False,
        'has_projects': False
    }
    
    github_path = f'{github_org}' if github_org else f'user' 
    url = f'https://api.github.com/repos/{github_path}/{github_name}'
    try:
        r = requests.patch(url, json=data, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Failed to patch github repository: "+gitlab_repo['path_with_namespace'])
        pprint(e.response.json(), stream=sys.stderr)
        raise SystemExit(e)

    return r.json()
