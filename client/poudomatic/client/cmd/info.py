from click import command, echo
from click.decorators import pass_meta_key

@command()
@pass_meta_key("client")
def info(client):
    results = client.info()
    echo(f"Portsbranches: {', '.join(results['portsbranches'])}")
    echo(f"Jails: {', '.join(results['jails'])}")
