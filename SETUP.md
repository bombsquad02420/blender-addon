# Setup

Instructions for setting up the dev environment

## Pre-reqs:

- VS Code with Remote Containers extension (`ms-vscode-remote.vscode-remote-extensionpack`)
- Docker
- Blender (I am using Flatpak)

> NOTE: Using docker is not a strict requirement, however it will take care of doing most of the setup for you

## Steps

### Installation

- Clone the repo

```bash
git clone --recursive https://github.com/bombsquad02420/blender-addon.git

cd blender-addon
```

- Install additional modules (for Blender to use)

```bash
pip install --target=modules -r requirements.blender.txt
```

### Blender

- Add the cloned folder (`blender-addon`) to Blender's `script` data path. `Edit` > `Preferences` > `File Path`

![Blender Preferences](.github/images/setup_blenderPreferences.png)

- Search for `debugger` in `Add-ons` panel and enable the `Debugger for VS Code` extension. Under the extension's preferences the path to `debugpy` should be auto-detected.

![Debugger Addon Preferences](.github/images/setup_blenderDebuggerAddonPreferences.png)

- Make sure the port is `5678` and timeout is set to a large enough value (in seconds)

### Docker 

- make sure the docker daemon is running and has proper priviledges (user must be added to the docker group. sudo must not be used)

- add links

### VS Code

- Open the folder in VS code and Click on open in container prompt. Wait for the setup. 

### Blender

- Restart Blender

- Search for debugger and start the debugger

### VS Code

- open `.vscode/launch.json` and replace `${localWorkspaceFolder}` with the path from step 1

```diff
      "pathMappings": [
        {
          "localRoot": "${workspaceFolder}",
-          "remoteRoot": "${localWorkspaceFolder}"
+          "remoteRoot": "/home/aryan/Projects/GitHub/bombsquad02420/blender-addon/"
        }
      ],
```

- In Debug Panel (`Ctrl + Shift + D`), start the debugger (`F5`).

![](.github/images/setup_vscLaunchDebugger.png)

- Debug Terminal will show connected message



