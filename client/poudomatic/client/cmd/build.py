from click import command, option, argument, echo
from click.decorators import pass_meta_key

@command()
@option("--nowait", is_flag=True, help="...")
@option("--repo", multiple=True)
@argument("jail_version")
@argument("ports_branch")
@argument("origins", nargs=-1)
@pass_meta_key("client")
def build(client, jail_version, ports_branch, origins, repo, nowait):
    task_id = client.build(jail_version, ports_branch, origins, repo)

    if nowait:
        click.echo(task_id)
        return

    for endpoint,msg in client.follow_log(task_id):
        if msg.get("origin") is None:
            echo(msg["msg"])

    origins = set()
    for result in client.get_result(task_id).values():
        if result["status"] == "success":
            origins.update(result["detail"].values())

    echo()

    if not origins:
        echo("No packages were built.")
    else:
        echo("To retrieve package build logs use:")
        for origin in sorted(origins):
            echo(f"  poudomatic buildlog {task_id} {origin}")

@command()
@argument("task_id")
@argument("origin", required=False)
@pass_meta_key("client")
def buildlog(client, task_id, origin):
    for endpoint,msg in client.follow_log(task_id):
        if msg.get("origin") == origin:
            echo(msg["msg"])
