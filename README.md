# JupyterHub Idle Culler Service

[![GitHub Workflow Status - Test](https://img.shields.io/github/workflow/status/jupyterhub/jupyterhub-idle-culler/Test?logo=github&label=tests)](https://github.com/jupyterhub/jupyterhub-idle-culler/actions)
[![Latest PyPI version](https://img.shields.io/pypi/v/jupyterhub-idle-culler?logo=pypi&logoColor=white)](https://pypi.python.org/pypi/jupyterhub-idle-culler)
[![GitHub](https://img.shields.io/badge/issue_tracking-github-blue?logo=github)](https://github.com/jupyterhub/jupyterhub-idle-culler/issues)
[![Discourse](https://img.shields.io/badge/help_forum-discourse-blue?logo=discourse)](https://discourse.jupyter.org/c/jupyterhub)
[![Gitter](https://img.shields.io/badge/social_chat-gitter-blue?logo=gitter)](https://gitter.im/jupyterhub/jupyterhub)

`jupyterhub-idle-culler` provides a JupyterHub service to identify and shut down idle or long-running Jupyter Notebook servers.
The exact actions performed are dependent on the used spawner for the Jupyter Notebook server (e.g. the default [LocalProcessSpawner](https://jupyterhub.readthedocs.io/en/stable/api/spawner.html#localprocessspawner>), [kubespawner](https://github.com/jupyterhub/kubespawner), or [dockerspawner](https://github.com/jupyterhub/dockerspawner)).
In addition, if explicitly requested, all users whose Jupyter Notebook servers have been shut down this way are deleted as JupyterHub users from the internal database. This neither affects the authentication method which continues to allow those users to log in nor does it delete persisted user data (e.g. stored in docker volumes for dockerspawner or in persisted volumes for kubespawner).

## Setup

### Installation

```bash
pip install jupyterhub-idle-culler
```

### As a hub managed service

In `jupyterhub_config.py`, add the following dictionary for the idle-culler
Service to the `c.JupyterHub.services` list:

```python
c.JupyterHub.services = [
    {
        'name': 'idle-culler',
        'admin': True,
        'command': [
            sys.executable,
            '-m', 'jupyterhub_idle_culler',
            '--timeout=3600'
        ],
    }
]
```

where:

- `'admin': True` indicates that the Service requires admin permissions so
  it can shut down arbitrary user notebooks, and
- `'command'` indicates that the Service will be managed by the Hub.

### As a standalone script

`jupyterhub-idle-culler` can also be run as a standalone script. It can
access the hub's api with a service token. The service token must have
admin privileges.

Generate an API token and store it in a `JUPYTERHUB_API_TOKEN` environment
variable. Then start `jupyterhub-idle-culler` manually

```bash
export JUPYTERHUB_API_TOKEN=$(jupyterhub token)
python3 -m jupyterhub-idle-culler [--timeout=900] [--url=http://localhost:8081/hub/api]
```

The command line interface also gives a quick overview of the different options for configuration.

```
  --concurrency                    Limit the number of concurrent requests made
                                   to the Hub.  Deleting a lot of users at the
                                   same time can slow down the Hub, so limit
                                   the number of API requests we have
                                   outstanding at any given time. (default 10)
  --cull-every                     The interval (in seconds) for checking for
                                   idle servers to cull. (default 0)
  --cull-users                     Cull users in addition to servers.  This is
                                   for use in temporary-user cases such as
                                   tmpnb. (default False)
  --internal-certs-location        The location of generated internal-ssl
                                   certificates (only needed with --ssl-
                                   enabled=true). (default internal-ssl)
  --max-age                        The maximum age (in seconds) of servers that
                                   should be culled even if they are active.
                                   (default 0)
  --remove-named-servers           Remove named servers in addition to stopping
                                   them.  This is useful for a BinderHub that
                                   uses authentication and named servers.
                                   (default False)
  --ssl-enabled                    Whether the Jupyter API endpoint has TLS
                                   enabled. (default False)
  --timeout                        The idle timeout (in seconds). (default 600)
  --url                            The JupyterHub API URL.
```

## Caveats

1. last_activity is not updated with high frequency, so cull timeout should be
   greater than the sum of:

   - single-user websocket ping interval (default: 30 seconds)
   - `JupyterHub.last_activity_interval` (default: 5 minutes)

2. The same `--timeout` and `--max-age` values are used to cull
   users and users' servers. If you want a different value for users and servers,
   you should add this script to the services list twice, just with different
   `name`s, different values, and one with the `--cull-users` option.

3. By default HTTP requests to the hub timeout after 60 seconds. This can be
   changed by setting the `JUPYTERHUB_REQUEST_TIMEOUT` environment variable.

## How it works

jupyterhub-idle-culler culls user servers using JupyterHub's REST API
([/users/{name}/server](https://jupyterhub.readthedocs.io/en/stable/_static/rest-api/index.html#operation--users--name--server-delete)
or
[/users/{name}/servers/{server_name}](https://jupyterhub.readthedocs.io/en/stable/_static/rest-api/index.html#operation--users--name--servers--server_name--delete)),
and makes the culling decisions based on its configuration and what JupyterHub
reports about the user servers via its REST API
[(/users)](https://jupyterhub.readthedocs.io/en/stable/_static/rest-api/index.html#path--users)
where user servers' `last_activity` is reported back.

The `last_activity` that JupyterHub reports is the most recent summary of
information updated at a regular interval via the [`update_last_activity`
function](https://github.com/jupyterhub/jupyterhub/blob/1.4.2/jupyterhub/app.py#L2646)
that combines two sources of information.

1. **The proxy's routes data**

   The `update_last_activity` function will [ask the
   proxy](https://jupyterhub.readthedocs.io/en/stable/reference/proxy.html#retrieving-routes)
   for the active routes like `/user/user1` and collects associated
   `last_activity` data if it is available. This activity represents
   successfully proxies network traffic.

   `last_activity` data for routes will be available when using
   [configurable-http-proxy](https://github.com/jupyterhub/configurable-http-proxy#readme)
   as JupyterHub does by default, but if for example
   [traefik-proxy](https://github.com/jupyterhub/traefik-proxy#readme) is used
   as it is in the [TLJH distribution](https://tljh.jupyter.org), no such data
   will be available.

2. **The user server's activity reports**

   The `update_last_activity` function also reads JupyterHub's database that
   keeps state about servers `last_activity`. These database records are updated
   whenever a server notifies JupyterHub about activity, as they are
   responsibility to do.

   Servers notify JupyterHub about activity by being started by the
   [`jupyterhub-singleuser`](https://github.com/jupyterhub/jupyterhub/blob/1.4.2/setup.py#L115)
   script that is made available by installing jupyterhub (or `jupyterhub-base`
   on conda-forge).

   The `jupyterhub-singleuser` script launches a modified server application
   that keeps JupyterHub updated with the server activity via the
   [`notify_activity`](https://github.com/jupyterhub/jupyterhub/blob/1.4.2/jupyterhub/singleuser/mixins.py#L497)
   function.

   The `notify_activity` function in turn make use of the server applications
   `last_activity` function (see implementation in
   [NotebookApp](https://github.com/jupyter/notebook/blob/v6.4.0/notebook/notebookapp.py#L392-L397)
   and
   [ServerApp](https://github.com/jupyter-server/jupyter_server/blob/v1.9.0/jupyter_server/serverapp.py#L375)
   respectively) that that combines information from API activity, kernel
   activity, kernel shutdown, and terminal activity. This activity also covers
   activity of applications like RStudio running via `jupyter-server-proxy`.

Here is a summary of what's described so far:

1. jupyterhub-idle-culler culls servers via JupyterHub's REST API.
2. jupyterhub-idle-culler makes decisions based on information retrieved by
   JupyterHub REST API.
3. JupyterHub REST API reports information regularly updated by summarizing
   information gained by: asking the proxy about routes' activity, and by
   retaining activity information reported by the servers.

Now, as the server's kernel activity influence the activity that servers will
notify JupyterHub about, the kernel activity in turn influences
jupyterhub-idle-culler. Due to this, it can be relevant to also learn a little
about a mechanism to _cull idle kernels_ as well even though
jupyterhub-idle-culler isn't involved in that.

The default kernel manager, the MappingKernelManager, can be configured to cull
idle kernels. Its configuration is documented in
[NotebookApp's](https://jupyter-notebook.readthedocs.io/en/stable/config.html#options)
and
[ServerApp's](https://jupyter-server.readthedocs.io/en/latest/full-config.html)
respective documentation, and here are some relevant kernel culling
configuration options:

- `MappingKernelManager.cull_busy`
- `MappingKernelManager.cull_idle_timeout`
- `MappingKernelManager.cull_interval`
- `MappingKernelManager.cull_connected`

  Note that `cull_connected` can be tricky to understand for JupyterLab as a
  browser having a web-socket connection to a kernel or not isn't as obvious as
  it was in the classical Jupyter notebook UI. See [this issue for more
  details](https://github.com/jupyterlab/jupyterlab/issues/6893).

  Also note that configuration of MappingKernelManager should be made on the
  user server itself, for example via a `jupyter_notebook_config.py` file in
  `/etc/jupyter` or `/usr/local/etc/jupyter` rather than where JupyterHub is
  running.

Finally, note that a Jupyter Notebook server can shut itself down without
without intervention by jupyterhub-idle-culler if
`NotebookApp.shutdown_no_activity_timeout` is configured.
