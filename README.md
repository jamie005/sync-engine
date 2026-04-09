# Sync Engine

## Project Setup

### Prerequisites

- A Linux-based computer
- VS Code
- Docker
- [VS Code Dev Containers Extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

### Steps

1. Within VSCode, open this repo then press CTRL+Shift+P to open the command pallette
2. Search for "Dev Containers: Reopen in Container" then select it
3. Once the Dev Container has successfully built, poetry should automatically install the package and create a virtual environment
4. When browsing the code, ensure the poetry virtual env is selected as your Python interpreter in the bottom left hand corner. It should be prefixed with "sync-engine"

### Commands

Running the Client:
```
poetry run client <target dir>
```

Running the Server:
```
poetry run server <target dir>
```

Running the Tests:
```
poetry run pytest tests/
```

Running the Linter:
```
poetry run flake8
```