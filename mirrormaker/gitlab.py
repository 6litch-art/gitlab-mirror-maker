import requests
from collections import OrderedDict
from urllib.parse import urlparse
import re

# GitLab api address
api = 'https://gitlab.com/api/v4'

# GitLab user authentication token
token = ''

def get_repos(visibility = '', archive = False, page = 1, fetch_next = True, strip = [], duplicates = False, namespaces = True):

    """Finds all public GitLab repositories of authenticated user.

    Returns:
     - List of public GitLab repositories.
    """
    page = 1 if not page else page
    fetch_next = True if not page else fetch_next

    gitlab_visibility = f"visibility={visibility}&" if visibility else ""
    gitlab_archived = "true" if archive else "false"

    url = api + f'/projects?{gitlab_visibility}owned=true&archived={gitlab_archived}&page={page}'
    headers = {'Authorization': f'Bearer {token}'}

    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)

    repos = r.json()

    if fetch_next:

        nextRepos = []
        nextPage = r.headers["X-Next-Page"] if "X-Next-Page" in r.headers else 0

        if nextPage: nextRepos = get_repos(visibility, archive, nextPage, fetch_next, strip, duplicates, namespaces)
        for repo in nextRepos:
            repos.append(repo)

    for i in range(len(repos)):
        
        if not namespaces:
            repos[i]["github_name"] = repos[i]['path']

        else:

            repos[i]["github_name"] = repos[i]['path_with_namespace'].split("/")
            for namespace in strip:
                if namespace in repos[i]["github_name"]:
                    repos[i]["github_name"].remove(namespace)
 
            repos[i]["github_name"] = '/'.join(repos[i]["github_name"]).replace("/", "-").split("-")
            if not duplicates:
                repos[i]["github_name"] = list(OrderedDict.fromkeys(repos[i]["github_name"]))

            repos[i]["github_name"] = '-'.join(repos[i]["github_name"])

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

def get_repos_by_shorthand(shorthand, visibility, archive, page, fetch_next = False, strip = [], duplicates = False, namespaces = True):

    repos_by_shorthand= []
    repos = get_repos(visibility, archive, page, fetch_next, strip, duplicates, namespaces)
    
    shorthand_pattern = re.compile("^"+shorthand+"$")

    for i in range(len(repos)):
        if shorthand_pattern.match(repos[i]["path_with_namespace"]):
            repos_by_shorthand.append(repos[i])

    if (len(repos_by_shorthand) == 0):
        print("Failed to find repository with pattern: "+shorthand + " (is it private/internal repository? use `--gitlab-private` if not set yet)")
        raise SystemExit(1)

    return repos_by_shorthand


def get_mirrors(gitlab_repo):
    """Finds all configured mirrors of GitLab repository.

    Args:
     - gitlab_repo: GitLab repository.

    Returns:
     - List of mirrors.
    """

    url = api + f'/projects/{gitlab_repo["id"]}/remote_mirrors'
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

def sync_remote(gitlab_repo): # Not implemented..

    o = urlparse(api)
    domain = o.scheme + "://" + o.netloc

    return domain + f'/{gitlab_repo["path_with_namespace"]}/-/settings/repository#js-push-remote-settings'
    
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

    #
    # Push mirror
    #
    url = api + f'/projects/{gitlab_repo["id"]}/remote_mirrors'

    headers = {'Authorization': f'Bearer {token}'}

    github_name = f'{github_org}' if github_org else f'{github_user}' 
    data = {
        'url': f'https://{github_user}:{github_token}@github.com/{github_name}/{gitlab_repo["github_name"]}.git',
        'enabled': True
    }

    try:
        r = requests.post(url, json=data, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Failed to push mirror repository: "+url)
        raise SystemExit(e)

    return r.json()

def pull_mirror(gitlab_repo, github_token, github_org, github_user):

    url = api + f'/projects/{gitlab_repo["id"]}/mirror/pull'
    headers = {'Authorization': f'Bearer {token}'}

    github_name = f'{github_org}' if github_org else f'{github_user}' 
    try:
        r = requests.post(url, headers=headers)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print("Failed to pull mirror repository, this is a premium feature.")

def delete_mirrors(gitlab_repo):
    """Delete a remote mirror in GitLab repository.

    For more details see: 
    https://docs.gitlab.com/ee/api/remote_mirrors.html#delete-a-remote-mirror

    Args:
     - gitlab_repo: GitLab repository to mirror.

    """

    mirrors = get_mirrors(gitlab_repo)
    for mirror in mirrors:

        url = api + f'/projects/{gitlab_repo["id"]}/remote_mirrors/{mirror["id"]}'

        headers = {'Authorization': f'Bearer {token}'}

        try:
            r = requests.delete(url, headers=headers)
            r.raise_for_status()
        except requests.exceptions.RequestException as e:
            print("Failed to mirror repository "+url)
            raise SystemExit(e)
