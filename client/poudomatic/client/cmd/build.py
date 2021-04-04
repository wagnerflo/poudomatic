import click
from ..api import API

@click.command()
@click.option("--nowait", is_flag=True, help="...")
@click.option("--portja", multiple=True)
@click.argument("jail_version")
@click.argument("ports_branch")
@click.argument("origins", nargs=-1)
def build(jail_version, ports_branch, origins, portja, nowait):
    api = API()
    task_id = api.generate_task_id()
    resp,data = api.req("PUT", f"build/{task_id}", {
        "jail_version": jail_version,
        "ports_branch": ports_branch,
        "origins": origins,
        "portja_targets": portja,
    })
    if resp.status != 200:
        click.echo(data)
        return

    if nowait:
        click.echo(task_id)
        return

    # todo
    click.echo(task_id)
