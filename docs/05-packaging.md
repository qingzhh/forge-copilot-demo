# 05 - Packaging & Deployment (v0.1)

## Goal

The engineering PC must not depend on a locally installed Python; the app
ships as a portable `exe` directory build.

## Recommended approach

Package with PyInstaller as a **onedir** build:

1. No dependency on the engineering PC having Python installed
2. More stable than a onefile build
3. Faster startup
4. Lower false-positive rate with antivirus software
5. Database and config files can sit next to the program directory

## Build command (on the development machine)

```powershell
.\scripts\build_portable_exe.bat
```

## Output

```text
dist\ForgeCopilot\
```

## Contents delivered to the engineering PC

Copy the whole directory, e.g. to `D:\ForgeCopilot\`. It contains:

- `ForgeCopilot.exe`
- Runtime dependency files
- `db\schema.sql`

On first run the program creates:

- `db\forge_install.db`

## Starting on the engineering PC

Double-click `ForgeCopilot.exe`.

## Deployment advice

1. Use a fixed directory on the engineering PC; do not move it around
2. The `db` directory needs write permission
3. Back up `db\forge_install.db` before every upgrade
4. When upgrading, replace only the program files; never overwrite the
   database
