import click
from ..api import API

@click.command()
@click.option("--nowait", is_flag=True, help="...")
@click.option("--portja")
@click.argument("jail_version")
@click.argument("ports_branch")
@click.argument("origin")
def depends(jail_version, ports_branch, origin, portja, nowait):
    api = API()
    task_id = api.generate_task_id()

    resp,data = api.req("PUT", f"depends/{task_id}", {
        "jail_version": jail_version,
        "ports_branch": ports_branch,
        "origin": origin,
        "portja_target": portja,
    })
    if resp.status != 200:
        click.echo(data)
        return

    if nowait:
        click.echo(task_id)
        return

    res = api.get_result(task_id)
    if res["status"] == "error":
        click.echo(res["detail"])
        return

    res = res["result"]

    def build_tree(origin):
        children = [
            build_tree(dep)
            for dep in sorted(
                res.get(origin, []),
                key=lambda k: len(res.get(k, [])),
                reverse=True
            )
        ]
        return { origin: children }

    def render_tree(tree, lvl=0, last=False):
        for origin,deps in tree.items():
            line = "│  " * (lvl - 1)
            if lvl:
                line += "└─ " if last else "├─ "
            line += origin
            yield line
            if deps:
                for dep in deps[:-1]:
                    for line in render_tree(dep, lvl+1):
                        yield line
                for line in render_tree(deps[-1], lvl+1, True):
                    yield line

    click.echo_via_pager("\n".join(render_tree(build_tree(origin))))
