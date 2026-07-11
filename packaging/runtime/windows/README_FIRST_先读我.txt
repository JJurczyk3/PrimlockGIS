PRIMELOCK GIS - WINDOWS PORTABLE EDITION
========================================

QUICK START / 快速开始

1. Extract the complete ZIP to a normal local folder.
   请先完整解压 ZIP 文件。
2. Double-click START_PRIMELOCK_GIS.bat for English.
   中文版请双击“启动_PRIMELOCK_GIS_中文版.bat”。
3. The Viewer and Support / Control windows open and connect automatically.

For complete Chinese instructions, read 先读我_中文版.txt.

No installation, Python, uv, PowerShell policy change, administrator access,
or internet connection is required.

To close the complete application, press q in the Support / Control window.
Keep the app folder and all files together.

If startup fails, open Command Prompt in this folder and run:

    app\PrimelockGIS.exe doctor --language en

External CSV datasets remain supported. In the Support / Control Admin panel,
enter:

    load dataset C:\full\path\to\your_dataset.csv

The bundled default dataset is read-only application data. Primelock GIS does
not write configuration or generated output into the extracted package.

WINDOWS SECURITY NOTE

PrimelockGIS.exe is not digitally signed because this coursework project does
not have a code-signing certificate. Windows SmartScreen may therefore show an
origin or reputation warning after the ZIP is downloaded. A reputation warning
is not the same as an antivirus malware detection. Do not disable Windows
security software. Verify the ZIP against SHA256SUMS.txt; if Windows Defender
reports an actual threat, do not run the application and ask the author or
course administrator to investigate.
