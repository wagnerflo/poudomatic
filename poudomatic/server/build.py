from re import compile as regex
from urllib.parse import urlparse

class Target:
    _registry = []

    @classmethod
    async def fetch(cls, uri):
        scheme = urlparse(uri).scheme
        for re,cls in cls._registry:
            if re.match(scheme):
                return await cls.new(uri)
        raise Exception()

    @classmethod
    def __init_subclass__(cls, /, scheme, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._registry.append((regex(scheme), cls))

class FileTarget(Target, scheme=r"^file$"):
    @classmethod
    async def new(cls, uri):
        self = cls()
        return self

class Build:
    def __init__(self, env, jail_version, ports_branch, target_uri):
        self.env = env
        self.jail_version = jail_version
        self.ports_branch = ports_branch
        self.target_uri = target_uri

    def __await__(self):
        return self.run().__await__()

    async def run(self):
        env = self.env
        jail = await env.get_jail(self.jail_version)
        ports = await env.get_ports(self.ports_branch)
        tgt = await Target.fetch(self.target_uri)

        # repo = Repository.clone_from_url(args.repository, config_context)
        # repos = { repo.url: repo }

        # async with ports.install() as portsname:
        #     async with jail.start() as j:
        #         pass
