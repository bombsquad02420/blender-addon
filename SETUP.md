# Setup

Instructions for setting up the dev environment

[Read Original](https://github.com/bombsquad02420/blender-debugger-for-vscode)

## Pre-reqs:

- VS Code
- Blender
- Python 3.10<sup>[1](#ref1)</sup>
- Python extension for VS Code (`ms-python.python`)<sup>[1](#ref1)</sup>
- Pylance extension for VS Code (`ms-python.vscode-pylance`)<sup>[1](#ref1)</sup>
- Docker<sup>[2](#ref2)</sup>
- Remote Containers extension for VS Code (`ms-vscode-remote.vscode-remote-extensionpack`)<sup>[2](#ref2)</sup>


## Steps

1. Clone the repo

    ```bash
    git clone --recursive https://github.com/bombsquad02420/blender-addon.git

    cd blender-addon
    ```

1. Install modules for development<sup>[1](#ref1)</sup>

    ```bash
    pip install -r requirements.txt
    ```

1. Install additional modules (for Blender to use)<sup>[1](#ref1)</sup>

    ```bash
    pip install --target=modules -r requirements.blender.txt
    ```

1. Add the repo's root folder (from STEP 1) to Blender's `script` data path. `Edit` > `Preferences` > `File Path`

    ![Blender Preferences](.github/images/setup_blenderPreferences.png)

1. Search for `debugger` in `Add-ons` panel and enable the `Debugger for VS Code` extension. Under the extension's preferences the path (from STEP 3) to `debugpy` should be auto-detected.

    ![Debugger Addon Preferences](.github/images/setup_blenderDebuggerAddonPreferences.png)

1. Make sure the port is `5678` and timeout is set to a large enough value.

1. Search for debugger and start the debugger

    ![Blender Start Debugger](.github/images/setup_blenderStartDebugger.png)

1. Open repo in VS Code

1. Open in Container<sup>[2](#ref2)</sup>

    Make sure the docker daemon is running and has proper priviledges (user must be added to the docker group. sudo must not be used)

    Click `Open in Container` in notification prompt

    ![VSCode Open in Container Prompt](.github/images/setup_vscOpenInContainer.png)

    Or use the Command Palette

    ![VSCode Open in Container Command Palette](.github/images/setup_vscOpenInContainerAlt.png)


1. In VSCode's Debug Panel (`Ctrl + Shift + D`), start the debugger (`F5`) with `Python: Blender Attach` configuration (or `Docker: Blender Attach` if using docker).

    ![VSCode Launch Debugger](.github/images/setup_vscLaunchDebugger.png)

1. VSCode's Debug Console and Blender Console should show attached message

    ![VSCode Debugger Attached](.github/images/setup_vscDebuggerAttached.png)

    ![Blender Debugger Attached](.github/images/setup_blenderDebuggerAttached.png)

# Other Stuff

1. Update submodules<sup>[1](#ref1)</sup>

    *TODO*

1. Auto-reload Blender scripts 

    *TODO*

# Notes

<span id="ref1">[1](#)</span>: Skip if using Docker Devcontainer

<span id="ref2">[2](#)</span>: Skip if **not** using Docker Devcontainer