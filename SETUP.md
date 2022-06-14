# Setup

Instructions for setting up the dev environment

## Pre-reqs:

- VS Code
- Blender
- Python 3.10
- *[optional]* Docker
- *[optional]* Remote Containers extension for VS Code (`ms-vscode-remote.vscode-remote-extensionpack`)


## Setup

1. Clone the repo

    ```bash
    git clone --recursive https://github.com/bombsquad02420/blender-addon.git

    cd blender-addon
    ```

1. Install additional modules (for Blender to use)

    > Skip this step if using Docker devcontainer

    ```bash
    pip install --target=modules -r requirements.blender.txt
    ```

1. Add the repo's root folder (from STEP 1) to Blender's `script` data path. `Edit` > `Preferences` > `File Path`

    ![Blender Preferences](.github/images/setup_blenderPreferences.png)

1. Search for `debugger` in `Add-ons` panel and enable the `Debugger for VS Code` extension. Under the extension's preferences the path (from STEP 2) to `debugpy` should be auto-detected.

    ![Debugger Addon Preferences](.github/images/setup_blenderDebuggerAddonPreferences.png)

1. Make sure the port is `5678` and timeout is set to a large enough value.

1. Search for debugger and start the debugger

    ![Blender Start Debugger](.github/images/setup_blenderStartDebugger.png)

1. Open repo in VS Code

1. Open in Container

    > Skip this step if not using docker / devcontainer

    Make sure the docker daemon is running and has proper priviledges (user must be added to the docker group. sudo must not be used)

    Click `Open in Container` in notification prompt

    ![VSCode Open in Container Prompt](.github/images/setup_vscOpenInContainer.png)

    Or use the Command Palette

    ![VSCode Open in Container Command Palette](.github/images/setup_vscOpenInContainerAlt.png)


1. In VSCode's Debug Panel (`Ctrl + Shift + D`), start the debugger (`F5`) with `Python: Blender Attach` configuration (or `Docker: Blender Attach` if using docker).

    ![VSCode Launch Debugger](.github/images/setup_vscLaunchDebugger.png)

1. Debug Terminal and Blender Console should show attached message

    ![VSCode Debugger Attached](.github/images/setup_vscDebuggerAttached.png)

    ![Blender Debugger Attached](.github/images/setup_blenderDebuggerAttached.png)



