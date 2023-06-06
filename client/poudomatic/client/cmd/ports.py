from click import group, command, option, argument, echo
from click.decorators import pass_meta_key

@command()
@option("--nowait", is_flag=True, help="...")
@pass_meta_key("client")
@argument("ports_branch")
def update(client, ports_branch, nowait):
    task_id = client.updateports(ports_branch)

    if nowait:
        click.echo(task_id)
        return

    for endpoint,msg in client.follow_log(task_id):
        echo(msg["msg"])


@group()
def ports():
    pass

ports.add_command(update)
