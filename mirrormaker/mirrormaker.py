import click
import requests
from tabulate import tabulate
from . import __version__
from . import gitlab
from . import github

@click.command(context_settings={'auto_envvar_prefix': 'MIRRORMAKER'})
@click.version_option(version=__version__)

@click.option('--github-token', required=True, help='GitHub authentication token')
@click.option('--github-user', required=True, help='GitHub username. If not provided, your GitLab username will be used by default.')
@click.option('--github-org', default=False, help='GitHub organisation. If not provided, your github personal repository will be used')
@click.option('--github-strip', help="Strip from github namespace some name parts")
@click.option('--github-no-duplicates/--github-duplicates', help="Strip from github namespace duplicated patterns")
@click.option('--github-no-namespaces/--github-namespaces', help="Keep gitlab namespaces from github namespace")

@click.option('--gitlab-token', required=True, help='GitLab authentication token')
@click.option('--gitlab-api', default=False, help='GitLab API address (by default, `https://gitlab.com/api/v4`)')
@click.option('--gitlab-private/--gitlab-public', default=False, help="Include private/internal repositories to GitHub (NB: `internal` becomes `private` visibility on GitHub)")
@click.option('--gitlab-archive/--no-gitlab-archive', default=False, help="Include archived repositories to GitHub")
@click.option('--gitlab-page', default=0, help="Only read a specific page on gitlab")

@click.option('--dry-run/--live', default=True, help="If enabled, a summary will be printed and no mirrors will be created.")
@click.option('--pull-mirrors/--push-mirrors-only', help="Pull modifications from github")
@click.option('--print-sync/--no-print-sync', default=False, help="Print link to the mirror section in Gitlab for further configuration")
@click.option('--delete-mirrors/--keep-mirrors', default=False, help="Delete remote mirror from GitLab. (this doesn't delete any repository on GitLab/GitHub)")
@click.option('--delete-from-github/--keep-repository-on-github', default=False, help="Delete remote repository from GitHub.")

@click.argument('repo', required=False)

def mirrormaker(github_token, github_user, github_org, github_strip, github_no_namespaces, github_no_duplicates, gitlab_token, gitlab_api, gitlab_private, gitlab_archive, gitlab_page, dry_run, pull_mirrors, delete_mirrors, delete_from_github, print_sync, repo=None):

    """
    Set up mirroring of repositories from GitLab to GitHub.

    By default, mirrors for all repositories owned by the user will be set up.

    If the REPO argument is given, a mirror will be set up for that repository
    only. REPO can be either a simple project name ("myproject"), in which case
    its namespace is assumed to be the current user, or the path of a project
    under a specific namespace ("mynamespace/myproject").
    """
    github.token = github_token
    github.org = github_org
    github.user = github_user
    github_strip = github_strip.split(" ") if github_strip else []
    github_duplicates = not github_no_duplicates
    github_namespaces = not github_no_namespaces

    gitlab.token = gitlab_token
    gitlab.api = gitlab_api
    gitlab_visibility = "public" if not gitlab_private else ""

    gitlab_page = 0 if repo else gitlab_page
    if repo:
        gitlab_repos = gitlab.get_repos_by_shorthand(repo, gitlab_visibility, gitlab_archive, gitlab_page, True if gitlab_page == 0 else False, github_strip, github_duplicates, github_namespaces)
    else:
        click.echo('Getting your GitLab repositories.. ', nl=False)
        gitlab_repos = gitlab.get_repos(gitlab_visibility, gitlab_archive, gitlab_page, True if gitlab_page == 0 else False, github_strip, github_duplicates, github_namespaces)
        if not gitlab_repos:
            click.echo('There are no repositories in your GitLab account.')
            return

    click.echo('Getting your GitHub repositories..')

    github_repos = github.get_repos(github_org)

    actions = find_actions_to_perform(github_org, gitlab_repos, github_repos, delete_mirrors, delete_from_github, pull_mirrors)
    print_summary_table(actions, print_sync)

    click.echo('Updating GitHub repositories.. ', nl=False)
    perform_actions(github_org, actions, dry_run, gitlab_visibility)

    click.echo('Done!')


def find_actions_to_perform(github_org, gitlab_repos, github_repos, delete_mirrors, delete_github, pull_mirrors):
    """Goes over provided repositories and figure out what needs to be done to create missing mirrors.

    Args:
     - gitlab_repos: List of GitLab repositories.
     - github_repos: List of GitHub repositories.

    Returns:
     - actions: List of actions necessary to perform on a GitLab repo to create a mirror
                eg: {'gitlab_repo: '', 'create_github': True, 'create_mirror': True}
    """

    actions = []
    with click.progressbar(gitlab_repos, label='Checking mirrors status', show_eta=False) as bar:

        for gitlab_repo in bar:
            action = check_mirror_status(gitlab_repo, github_repos, delete_mirrors, delete_github, pull_mirrors)
            actions.append(action)

    return actions


def check_mirror_status(gitlab_repo, github_repos, delete_mirrors, delete_github, pull_mirrors):
    """Checks if given GitLab repository has a mirror created among the given GitHub repositories. 

    Args:
     - gitlab_repo: GitLab repository.
     - github_repos: List of GitHub repositories.
     - delete_mirrors: Delete existing mirror links on GitLab
     - delete_github: Delete target repository on GitHub

    Returns:
     - action: Action necessary to perform on a GitLab repo to create a mirror (see find_actions_to_perform())
    """

    action = {
        'gitlab_repo': gitlab_repo,
        'create_github': True, 'delete_github': delete_github, 'patch_github': False,
        'create_mirror': True, 'delete_mirrors': delete_mirrors, 'pull_mirrors': pull_mirrors
    }

    mirrors = gitlab.get_mirrors(gitlab_repo)

    if gitlab.mirror_target_exists(github_repos, mirrors):
        action['create_mirror'] = False

    if github.repo_exists(github_repos, gitlab_repo["github_name"]):
        action['create_github'] = False
        action['patch_github'] = True

    return action

def print_summary_table(actions, print_sync = False):
    """Prints a table summarizing whether mirrors are already created or missing
    """

    click.echo("\nPrint table summary before modification:")

    created = click.style(u'\u2714 found', fg='green')
    missing = click.style(u'\u2718 not found', fg='red')

    headers = ['GitLab repo', 'Visibility', 'Archived', 'GitHub repo', 'Mirror']
    if(print_sync): headers.append("Sync link")

    summary = []
    for action in actions:
        row = [action["gitlab_repo"]["path_with_namespace"]]
        row.append(action["gitlab_repo"]["visibility"])
        row.append(action["gitlab_repo"]["archived"])
        row.append(action["gitlab_repo"]["github_name"]+" "+missing) if action["create_github"] else row.append(action["gitlab_repo"]["github_name"]+" "+created)
        row.append(missing) if action["create_mirror"] else row.append(created)
        if(print_sync): 
            row.append(gitlab.sync_remote(action["gitlab_repo"]))
        summary.append(row)

    summary.sort()

    click.echo(tabulate(summary, headers) + '\n')

def perform_actions(github_org, actions, dry_run, gitlab_visibility):
    """Creates GitHub repositories and configures GitLab mirrors where necessary. 

    Args:
     - actions: List of actions to perform, either creating GitHub repo and/or configuring GitLab mirror.
     - dry_run (bool): When True the actions are not performed.
    """

    if dry_run:
        click.echo('Run without the --apply flag to create missing repositories and mirrors.')
        return

    with click.progressbar(actions, label='Processing mirrors', show_eta=False) as bar:
        for action in bar:

            if action["delete_github"]:
                github.delete_repo(action["gitlab_repo"], github_org)
            elif action["create_github"]:
                github.create_repo(action["gitlab_repo"], github_org)
            elif action["patch_github"]:
                github.patch_repo(action["gitlab_repo"], github_org)

            if action["delete_mirrors"]:
                gitlab.delete_mirrors(action["gitlab_repo"])
            else:
                if action["create_mirror"]:
                    gitlab.create_mirror(action["gitlab_repo"], github.token, github.org, github.user)
                if action["pull_mirrors"]:
                    gitlab.pull_mirror(action["gitlab_repo"], github.token, github.org, github.user)

if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter, unexpected-keyword-arg
    mirrormaker()
